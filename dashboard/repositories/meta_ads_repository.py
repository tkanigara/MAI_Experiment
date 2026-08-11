from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import text

try:
    from dashboard.db import create_db_engine
    from dashboard.services.ads_workspace import (
        ADS_GOAL_DEFINITIONS,
        ADS_PLATFORM_KEYS,
        ads_period_configuration,
        ads_platform_catalog,
        ads_product_configuration,
    )
except ModuleNotFoundError:
    from db import create_db_engine
    from services.ads_workspace import (
        ADS_GOAL_DEFINITIONS,
        ADS_PLATFORM_KEYS,
        ads_period_configuration,
        ads_platform_catalog,
        ads_product_configuration,
    )


TABLES = {
    "campaign": "meta_ads_campaign_performance",
    "adset": "meta_ads_adset_performance",
    "ad": "meta_ads_ad_performance",
    "placement": "meta_ads_placement_breakdown",
    "demographic": "meta_ads_demographic_breakdown",
    "region": "meta_ads_region_breakdown",
}

META_GOAL_RESULT_TYPES = {
    "reach": ("reach",),
    "engagement": ("actions:post_interaction_gross", "post_engagement"),
    "profile_visits": ("profile_visit_view", "profile_visit"),
    "page_likes": ("page_like", "page_likes", "actions:page_like"),
}

COMMON_FIELDS = (
    "source_row_key",
    "source_row_number",
    "reporting_start",
    "reporting_end",
    "delivery_status",
    "result_value",
    "result_type",
    "cost_per_result",
    "budget",
    "budget_source",
    "budget_type",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "post_engagements",
    "link_clicks",
    "link_ctr",
    "instagram_follows",
    "page_engagements",
    "reaction_reach",
    "attribution_setting",
    "start_date",
    "end_value",
    "bid",
    "bid_type",
    "last_significant_edit",
    "quality_ranking",
    "engagement_rate_ranking",
    "conversion_rate_ranking",
    "initial_result_value",
    "initial_result_type",
)

TABLE_FIELDS = {
    "campaign": (
        "campaign_external_id",
        "campaign_name",
        *COMMON_FIELDS,
    ),
    "adset": (
        "campaign_performance_id",
        "campaign_external_id",
        "campaign_name",
        "adset_external_id",
        "adset_name",
        *COMMON_FIELDS,
    ),
    "ad": (
        "campaign_performance_id",
        "adset_performance_id",
        "campaign_external_id",
        "campaign_name",
        "adset_external_id",
        "adset_name",
        "ad_external_id",
        "ad_name",
        *COMMON_FIELDS,
    ),
    "placement": (
        "ad_performance_id",
        "campaign_external_id",
        "campaign_name",
        "adset_external_id",
        "adset_name",
        "ad_external_id",
        "ad_name",
        "publisher_platform",
        "placement",
        "device_platform",
        *COMMON_FIELDS,
    ),
    "demographic": (
        "ad_performance_id",
        "campaign_external_id",
        "campaign_name",
        "adset_external_id",
        "adset_name",
        "ad_external_id",
        "ad_name",
        "age",
        "gender",
        *COMMON_FIELDS,
    ),
    "region": (
        "ad_performance_id",
        "campaign_external_id",
        "campaign_name",
        "adset_external_id",
        "adset_name",
        "ad_external_id",
        "ad_name",
        "region",
        *COMMON_FIELDS,
    ),
}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class MetaAdsRepository:
    def __init__(self, engine=None):
        self.engine = engine or create_db_engine()

    def import_snapshot(
        self,
        *,
        client_id: str,
        requested_period_id: str | None,
        period_start: date,
        period_end: date,
        files: dict,
        diagnostics: dict,
        warnings: list[str],
    ) -> dict:
        UUID(client_id)
        if requested_period_id:
            UUID(requested_period_id)

        with self.engine.begin() as conn:
            client = conn.execute(
                text("SELECT id FROM clients WHERE id = CAST(:client_id AS UUID) FOR UPDATE"),
                {"client_id": client_id},
            ).mappings().first()
            if not client:
                raise ValueError("Client was not found.")

            conn.execute(
                text(
                    """
                    INSERT INTO client_products (client_id, product)
                    VALUES (CAST(:client_id AS UUID), 'meta_ads')
                    ON CONFLICT (client_id, product)
                    DO UPDATE SET is_active = TRUE, updated_at = now()
                    """
                ),
                {"client_id": client_id},
            )

            if requested_period_id:
                period = conn.execute(
                    text(
                        """
                        SELECT id, period_start, period_end
                        FROM meta_ads_report_periods
                        WHERE id = CAST(:period_id AS UUID)
                          AND client_id = CAST(:client_id AS UUID)
                        FOR UPDATE
                        """
                    ),
                    {"period_id": requested_period_id, "client_id": client_id},
                ).mappings().first()
                if not period:
                    raise ValueError("Report period was not found for this client.")
                if period["period_start"] != period_start or period["period_end"] != period_end:
                    raise ValueError(
                        "CSV reporting dates do not match the selected report period."
                    )
                period_id = period["id"]
            else:
                period_id = conn.execute(
                    text(
                        """
                        INSERT INTO meta_ads_report_periods (
                            client_id, period_start, period_end, period_label
                        )
                        VALUES (
                            CAST(:client_id AS UUID), :period_start, :period_end,
                            to_char(CAST(:period_start AS DATE), 'FMMonth YYYY')
                        )
                        ON CONFLICT (client_id, period_start, period_end)
                        DO UPDATE SET period_label = EXCLUDED.period_label
                        RETURNING id
                        """
                    ),
                    {
                        "client_id": client_id,
                        "period_start": period_start,
                        "period_end": period_end,
                    },
                ).scalar_one()

            filenames = {file_type: parsed.filename for file_type, parsed in files.items()}
            import_id = conn.execute(
                text(
                    """
                    INSERT INTO meta_ads_imports (
                        client_id, meta_ads_report_period_id, platform,
                        source, status, filenames, summary_totals,
                        diagnostics, warnings, imported_at
                    )
                    VALUES (
                        CAST(:client_id AS UUID), :period_id, 'meta',
                        'csv', 'running', CAST(:filenames AS JSONB),
                        CAST(:summary_totals AS JSONB),
                        CAST(:diagnostics AS JSONB), CAST(:warnings AS JSONB), now()
                    )
                    ON CONFLICT (client_id, meta_ads_report_period_id, platform)
                    DO UPDATE SET
                        source = EXCLUDED.source,
                        status = EXCLUDED.status,
                        filenames = EXCLUDED.filenames,
                        summary_totals = EXCLUDED.summary_totals,
                        diagnostics = EXCLUDED.diagnostics,
                        warnings = EXCLUDED.warnings,
                        error_message = NULL,
                        imported_at = EXCLUDED.imported_at,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "client_id": client_id,
                    "period_id": period_id,
                    "filenames": _json(filenames),
                    "summary_totals": _json(diagnostics.get("canonical_totals", {})),
                    "diagnostics": _json(diagnostics),
                    "warnings": _json(warnings),
                },
            ).scalar_one()

            # A period is a snapshot. Delete in dependency order and insert the
            # six freshly validated files in the same transaction.
            for file_type in (
                "placement",
                "demographic",
                "region",
                "ad",
                "adset",
                "campaign",
            ):
                conn.execute(
                    text(f"DELETE FROM {TABLES[file_type]} WHERE import_id = :import_id"),
                    {"import_id": import_id},
                )

            counts = {}
            for file_type, parsed in files.items():
                counts[file_type] = self._insert_rows(
                    conn,
                    file_type=file_type,
                    import_id=import_id,
                    client_id=client_id,
                    period_id=period_id,
                    rows=parsed.rows,
                )

            conn.execute(
                text(
                    """
                    UPDATE meta_ads_imports
                    SET status = 'success', updated_at = now()
                    WHERE id = :import_id
                    """
                ),
                {"import_id": import_id},
            )

        return {
            "import_id": import_id,
            "meta_ads_report_period_id": period_id,
            "counts": counts,
        }

    def client_periods(self, client_id: str) -> dict:
        UUID(client_id)
        with self.engine.connect() as conn:
            client = conn.execute(
                text(
                    """
                    SELECT
                        c.id, c.client_code, c.client_name, c.industry,
                        cp.configuration AS ads_configuration,
                        ARRAY(
                            SELECT active_product.product
                            FROM client_products active_product
                            WHERE active_product.client_id = c.id
                              AND active_product.is_active
                            ORDER BY active_product.product
                        ) AS products
                    FROM clients c
                    JOIN client_products cp
                      ON cp.client_id = c.id
                     AND cp.product = 'meta_ads'
                     AND cp.is_active
                    WHERE c.id = CAST(:client_id AS UUID)
                      AND c.is_active
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            if not client:
                raise ValueError("Ads client was not found.")
            client = dict(client)
            raw_product_configuration = client.get("ads_configuration") or None
            legacy_goal_configuration = (
                raw_product_configuration
                if isinstance(raw_product_configuration, dict)
                and (
                    raw_product_configuration.get("goals")
                    or raw_product_configuration.get("ads_goals")
                )
                else None
            )
            configuration = ads_product_configuration(raw_product_configuration)
            client["ads_configuration"] = configuration
            client["ads_platforms"] = configuration["platforms"]
            rows = conn.execute(
                text(
                    """
                    SELECT
                        p.id,
                        p.period_start,
                        p.period_end,
                        p.period_label,
                        p.configuration AS ads_configuration,
                        LOWER(REPLACE(p.period_label, ' ', '-')) AS slug,
                        p.status AS period_status,
                        i.id AS import_id,
                        i.status AS import_status,
                        i.imported_at,
                        i.filenames,
                        i.warnings,
                        i.diagnostics,
                        (SELECT COUNT(*) FROM meta_ads_campaign_performance r WHERE r.import_id = i.id) AS campaigns,
                        (SELECT COUNT(*) FROM meta_ads_adset_performance r WHERE r.import_id = i.id) AS adsets,
                        (SELECT COUNT(*) FROM meta_ads_ad_performance r WHERE r.import_id = i.id) AS ads,
                        (SELECT COUNT(*) FROM meta_ads_placement_breakdown r WHERE r.import_id = i.id) AS placements,
                        (SELECT COUNT(*) FROM meta_ads_demographic_breakdown r WHERE r.import_id = i.id) AS demographics,
                        (SELECT COUNT(*) FROM meta_ads_region_breakdown r WHERE r.import_id = i.id) AS regions
                    FROM meta_ads_report_periods p
                    LEFT JOIN meta_ads_imports i
                      ON i.meta_ads_report_period_id = p.id
                     AND i.platform = 'meta'
                    WHERE p.client_id = CAST(:client_id AS UUID)
                    ORDER BY p.period_start DESC, p.created_at DESC
                    """
                ),
                {"client_id": client_id},
            ).mappings()
            periods = []
            for row in rows:
                period = dict(row)
                period["label"] = period.get("period_label")
                period["status"] = period.get("import_status") or "No import"
                period["uploaded_files"] = len(period.get("filenames") or {})
                period["platforms"] = configuration["platforms"]
                period_configuration = ads_period_configuration(
                    period.get("ads_configuration") or legacy_goal_configuration,
                    configuration["platforms"],
                )
                period["ads_configuration"] = period_configuration
                period["goals"] = period_configuration["goals"]
                period["platform_catalog"] = ads_platform_catalog(
                    configuration,
                    period_configuration,
                )
                periods.append(period)
            return {
                "client": client,
                "platforms": ads_platform_catalog(configuration),
                "periods": periods,
            }

    def platform_detail(self, client_id: str, period_id: str, platform: str) -> dict:
        UUID(client_id)
        UUID(period_id)
        platform = str(platform or "").strip().lower()
        if platform not in ADS_PLATFORM_KEYS:
            raise ValueError("Unsupported Ads platform.")

        with self.engine.connect() as conn:
            context = conn.execute(
                text(
                    """
                    SELECT
                        c.id AS client_id,
                        c.client_name,
                        cp.configuration AS ads_configuration,
                        p.configuration AS period_configuration,
                        p.id AS period_id,
                        p.period_label,
                        p.period_start,
                        p.period_end,
                        i.id AS import_id,
                        i.status AS import_status,
                        i.imported_at
                    FROM clients c
                    JOIN client_products cp
                      ON cp.client_id = c.id
                     AND cp.product = 'meta_ads'
                     AND cp.is_active
                    JOIN meta_ads_report_periods p
                      ON p.client_id = c.id
                     AND p.id = CAST(:period_id AS UUID)
                    LEFT JOIN meta_ads_imports i
                      ON i.meta_ads_report_period_id = p.id
                     AND i.platform = 'meta'
                    WHERE c.id = CAST(:client_id AS UUID)
                      AND c.is_active
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
            if not context:
                raise ValueError("Ads report period was not found.")

            context = dict(context)
            raw_product_configuration = context.get("ads_configuration") or None
            legacy_goal_configuration = (
                raw_product_configuration
                if isinstance(raw_product_configuration, dict)
                and (
                    raw_product_configuration.get("goals")
                    or raw_product_configuration.get("ads_goals")
                )
                else None
            )
            configuration = ads_product_configuration(raw_product_configuration)
            if platform not in configuration["platforms"]:
                raise ValueError("Ads platform is not connected for this client.")
            period_configuration = ads_period_configuration(
                context.get("period_configuration") or legacy_goal_configuration,
                configuration["platforms"],
            )

            definition = next(
                item
                for item in ads_platform_catalog(configuration, period_configuration)
                if item["key"] == platform
            )
            response = {
                "platform": definition,
                "period": {
                    key: context.get(key)
                    for key in (
                        "period_id",
                        "period_label",
                        "period_start",
                        "period_end",
                        "import_status",
                        "imported_at",
                    )
                },
                "data_status": "not_configured"
                if not definition["active_goals"]
                else "coming_soon"
                if definition["ingestion_status"] != "available"
                else "missing_data",
                "goals": [],
            }
            if not definition["active_goals"]:
                return response
            if definition["ingestion_status"] != "available":
                return response
            if not context.get("import_id") or context.get("import_status") != "success":
                return response

            for goal_config in period_configuration["goals"].get(platform, []):
                goal_key = goal_config["key"]
                result_types = list(META_GOAL_RESULT_TYPES.get(goal_key, ()))
                goal_definition = next(
                    item
                    for item in ADS_GOAL_DEFINITIONS[platform]
                    if item["key"] == goal_key
                )
                primary_metric = (
                    "post_engagements" if goal_key == "engagement" else "result_value"
                )
                totals = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(SUM({primary_metric}), 0) AS result_value,
                            COALESCE(SUM(spend), 0) AS spend,
                            COALESCE(SUM(impressions), 0) AS impressions,
                            COALESCE(SUM(reach), 0) AS reach,
                            COALESCE(SUM(post_engagements), 0) AS engagements,
                            COALESCE(SUM(link_clicks), 0) AS link_clicks,
                            COALESCE(SUM(instagram_follows), 0) AS follows,
                            COALESCE(SUM(page_engagements), 0) AS page_engagements
                        FROM meta_ads_placement_breakdown
                        WHERE import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        """
                    ),
                    {
                        "import_id": context["import_id"],
                        "platform": platform,
                        "result_types": result_types,
                    },
                ).mappings().one()
                totals = dict(totals)
                numeric = {
                    key: float(value or 0)
                    for key, value in totals.items()
                }
                result_value = numeric["result_value"]
                spend = numeric["spend"]
                impressions = numeric["impressions"]
                reach = numeric["reach"]
                engagements = numeric["engagements"]
                follows = numeric["follows"]
                monthly_target = goal_config.get("target_monthly")
                monthly_budget = goal_config.get("budget_monthly")
                numeric.update({
                    "frequency": impressions / reach if reach else None,
                    "ctr": numeric["link_clicks"] / impressions * 100 if impressions else None,
                    "engagement_rate": engagements / impressions * 100 if impressions else None,
                    "cost_per_result": spend / result_value if result_value else None,
                    "cost_per_thousand_reached": spend / reach * 1000 if reach else None,
                    "visit_to_follow_rate": follows / result_value * 100
                    if goal_key == "profile_visits" and result_value
                    else None,
                })

                cumulative = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(SUM(r.{primary_metric}), 0) AS result_value,
                            COALESCE(SUM(r.spend), 0) AS spend
                        FROM meta_ads_placement_breakdown r
                        JOIN meta_ads_report_periods p
                          ON p.id = r.meta_ads_report_period_id
                        WHERE r.client_id = CAST(:client_id AS UUID)
                          AND p.period_end <= CAST(:period_end AS DATE)
                          AND LOWER(COALESCE(r.publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(r.result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        """
                    ),
                    {
                        "client_id": client_id,
                        "period_end": context["period_end"],
                        "platform": platform,
                        "result_types": result_types,
                    },
                ).mappings().one()

                base_parameters = {
                    "import_id": context["import_id"],
                    "platform": platform,
                    "result_types": result_types,
                }
                creatives = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(NULLIF(ad_name, ''), 'Unnamed ad') AS label,
                            COALESCE(SUM({primary_metric}), 0) AS result_value,
                            COALESCE(SUM(reach), 0) AS reach,
                            COALESCE(SUM(impressions), 0) AS impressions,
                            COALESCE(SUM(post_engagements), 0) AS engagements,
                            COALESCE(SUM(link_clicks), 0) AS link_clicks,
                            COALESCE(SUM(spend), 0) AS spend
                        FROM meta_ads_placement_breakdown
                        WHERE import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        GROUP BY COALESCE(NULLIF(ad_name, ''), 'Unnamed ad')
                        ORDER BY result_value DESC, spend DESC
                        LIMIT 10
                        """
                    ),
                    base_parameters,
                ).mappings()
                placements = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(NULLIF(placement, ''), 'Unknown placement') AS label,
                            COALESCE(SUM({primary_metric}), 0) AS result_value,
                            COALESCE(SUM(impressions), 0) AS impressions,
                            COALESCE(SUM(spend), 0) AS spend
                        FROM meta_ads_placement_breakdown
                        WHERE import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        GROUP BY COALESCE(NULLIF(placement, ''), 'Unknown placement')
                        ORDER BY result_value DESC, impressions DESC
                        LIMIT 10
                        """
                    ),
                    base_parameters,
                ).mappings()
                demographic_metric = primary_metric
                region_breakdown_metric = (
                    "link_clicks" if goal_key == "profile_visits" else primary_metric
                )
                demographic = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(NULLIF(age, ''), 'Unknown') AS age,
                            COALESCE(NULLIF(gender, ''), 'Unknown') AS gender,
                            COALESCE(SUM({demographic_metric}), 0) AS result_value
                        FROM meta_ads_demographic_breakdown
                        WHERE import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        GROUP BY COALESCE(NULLIF(age, ''), 'Unknown'), COALESCE(NULLIF(gender, ''), 'Unknown')
                        ORDER BY result_value DESC
                        LIMIT 12
                        """
                    ),
                    {"import_id": context["import_id"], "result_types": result_types},
                ).mappings()
                regions = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(NULLIF(region, ''), 'Unknown') AS label,
                            COALESCE(SUM({region_breakdown_metric}), 0) AS result_value
                        FROM meta_ads_region_breakdown
                        WHERE import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        GROUP BY COALESCE(NULLIF(region, ''), 'Unknown')
                        ORDER BY result_value DESC
                        LIMIT 10
                        """
                    ),
                    {"import_id": context["import_id"], "result_types": result_types},
                ).mappings()

                response["goals"].append({
                    **goal_definition,
                    "targets": goal_config,
                    "metrics": numeric,
                    "achievement": result_value / float(monthly_target) * 100
                    if monthly_target
                    else None,
                    "budget_use": spend / float(monthly_budget) * 100
                    if monthly_budget
                    else None,
                    "cumulative": {
                        "result_value": float(cumulative["result_value"] or 0),
                        "spend": float(cumulative["spend"] or 0),
                    },
                    "creatives": [dict(row) for row in creatives],
                    "placements": [dict(row) for row in placements],
                    "demographics": [dict(row) for row in demographic],
                    "regions": [dict(row) for row in regions],
                    "breakdown_scope": "shared_meta",
                    "region_metric": "link_clicks_proxy"
                    if goal_key == "profile_visits"
                    else "goal_result",
                })

            response["data_status"] = "ready"
            return response

    def period_overview(self, client_id: str, period_id: str) -> dict:
        UUID(client_id)
        UUID(period_id)
        with self.engine.connect() as conn:
            context = conn.execute(
                text(
                    """
                    SELECT
                        cp.configuration AS ads_configuration,
                        p.configuration AS period_configuration,
                        p.period_label,
                        p.period_end,
                        i.id AS import_id,
                        i.status AS import_status
                    FROM client_products cp
                    JOIN meta_ads_report_periods p
                      ON p.client_id = cp.client_id
                     AND p.id = CAST(:period_id AS UUID)
                    LEFT JOIN meta_ads_imports i
                      ON i.meta_ads_report_period_id = p.id
                     AND i.platform = 'meta'
                    WHERE cp.client_id = CAST(:client_id AS UUID)
                      AND cp.product = 'meta_ads'
                      AND cp.is_active
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
            if not context:
                raise ValueError("Ads report period was not found.")
            raw_product_configuration = context.get("ads_configuration") or None
            legacy_goal_configuration = (
                raw_product_configuration
                if isinstance(raw_product_configuration, dict)
                and (
                    raw_product_configuration.get("goals")
                    or raw_product_configuration.get("ads_goals")
                )
                else None
            )
            configuration = ads_product_configuration(raw_product_configuration)
            period_configuration = ads_period_configuration(
                context.get("period_configuration") or legacy_goal_configuration,
                configuration["platforms"],
            )
            historical_periods = conn.execute(
                text(
                    """
                    SELECT configuration
                    FROM meta_ads_report_periods
                    WHERE client_id = CAST(:client_id AS UUID)
                      AND period_end <= CAST(:period_end AS DATE)
                    ORDER BY period_end
                    """
                ),
                {"client_id": client_id, "period_end": context["period_end"]},
            ).scalars().all()
            cumulative_targets = {}
            for historical in historical_periods:
                historical_configuration = ads_period_configuration(
                    historical or legacy_goal_configuration,
                    configuration["platforms"],
                )
                for historical_platform, goals in historical_configuration["goals"].items():
                    for historical_goal in goals:
                        key = (historical_platform, historical_goal["key"])
                        target = cumulative_targets.setdefault(
                            key, {"target": 0, "budget": 0, "has_target": False, "has_budget": False}
                        )
                        if historical_goal.get("target_monthly") is not None:
                            target["target"] += float(historical_goal["target_monthly"])
                            target["has_target"] = True
                        if historical_goal.get("budget_monthly") is not None:
                            target["budget"] += float(historical_goal["budget_monthly"])
                            target["has_budget"] = True
            rows = []
            catalog = {
                item["key"]: item
                for item in ads_platform_catalog(configuration, period_configuration)
            }
            for platform in configuration["platforms"]:
                definition = catalog[platform]
                for goal_config in period_configuration["goals"].get(platform, []):
                    goal_key = goal_config["key"]
                    goal_definition = next(
                        item
                        for item in ADS_GOAL_DEFINITIONS[platform]
                        if item["key"] == goal_key
                    )
                    row = {
                        "platform": platform,
                        "platform_label": definition["label"],
                        "goal_key": goal_key,
                        "goal_label": goal_definition["label"],
                        "target_monthly": goal_config.get("target_monthly"),
                        "target_total": cumulative_targets.get((platform, goal_key), {}).get("target")
                        if cumulative_targets.get((platform, goal_key), {}).get("has_target")
                        else None,
                        "budget_monthly": goal_config.get("budget_monthly"),
                        "budget_total": cumulative_targets.get((platform, goal_key), {}).get("budget")
                        if cumulative_targets.get((platform, goal_key), {}).get("has_budget")
                        else None,
                        "actual_monthly": None,
                        "actual_total": None,
                        "spend_monthly": None,
                        "spend_total": None,
                        "achievement_monthly": None,
                        "achievement_total": None,
                        "budget_use_monthly": None,
                        "budget_use_total": None,
                        "status": "coming_soon"
                        if definition["ingestion_status"] != "available"
                        else "missing_data",
                    }
                    if (
                        definition["ingestion_status"] == "available"
                        and context.get("import_id")
                        and context.get("import_status") == "success"
                    ):
                        result_types = list(META_GOAL_RESULT_TYPES.get(goal_key, ()))
                        primary_metric = (
                            "post_engagements"
                            if goal_key == "engagement"
                            else "result_value"
                        )
                        monthly = conn.execute(
                            text(
                                f"""
                                SELECT
                                    COALESCE(SUM({primary_metric}), 0) AS actual,
                                    COALESCE(SUM(spend), 0) AS spend
                                FROM meta_ads_placement_breakdown
                                WHERE import_id = CAST(:import_id AS UUID)
                                  AND LOWER(COALESCE(publisher_platform, '')) = :platform
                                  AND LOWER(COALESCE(result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                                """
                            ),
                            {
                                "import_id": context["import_id"],
                                "platform": platform,
                                "result_types": result_types,
                            },
                        ).mappings().one()
                        cumulative = conn.execute(
                            text(
                                f"""
                                SELECT
                                    COALESCE(SUM(r.{primary_metric}), 0) AS actual,
                                    COALESCE(SUM(r.spend), 0) AS spend
                                FROM meta_ads_placement_breakdown r
                                JOIN meta_ads_report_periods p
                                  ON p.id = r.meta_ads_report_period_id
                                WHERE r.client_id = CAST(:client_id AS UUID)
                                  AND p.period_end <= CAST(:period_end AS DATE)
                                  AND LOWER(COALESCE(r.publisher_platform, '')) = :platform
                                  AND LOWER(COALESCE(r.result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                                """
                            ),
                            {
                                "client_id": client_id,
                                "period_end": context["period_end"],
                                "platform": platform,
                                "result_types": result_types,
                            },
                        ).mappings().one()
                        actual_monthly = float(monthly["actual"] or 0)
                        spend_monthly = float(monthly["spend"] or 0)
                        actual_total = float(cumulative["actual"] or 0)
                        spend_total = float(cumulative["spend"] or 0)
                        row.update({
                            "actual_monthly": actual_monthly,
                            "actual_total": actual_total,
                            "spend_monthly": spend_monthly,
                            "spend_total": spend_total,
                            "achievement_monthly": actual_monthly / float(row["target_monthly"]) * 100
                            if row["target_monthly"]
                            else None,
                            "achievement_total": actual_total / float(row["target_total"]) * 100
                            if row["target_total"]
                            else None,
                            "budget_use_monthly": spend_monthly / float(row["budget_monthly"]) * 100
                            if row["budget_monthly"]
                            else None,
                            "budget_use_total": spend_total / float(row["budget_total"]) * 100
                            if row["budget_total"]
                            else None,
                            "status": "ready",
                        })
                    rows.append(row)
            return {
                "period_id": period_id,
                "period_label": context["period_label"],
                "rows": rows,
            }

    def update_period_configuration(
        self, client_id: str, period_id: str, payload: dict | None
    ) -> dict:
        UUID(client_id)
        UUID(period_id)
        with self.engine.begin() as conn:
            context = conn.execute(
                text(
                    """
                    SELECT cp.configuration AS ads_configuration
                    FROM client_products cp
                    JOIN meta_ads_report_periods p
                      ON p.client_id = cp.client_id
                     AND p.id = CAST(:period_id AS UUID)
                    WHERE cp.client_id = CAST(:client_id AS UUID)
                      AND cp.product = 'meta_ads'
                      AND cp.is_active
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
            if not context:
                raise ValueError("Ads report period was not found.")

            product_configuration = ads_product_configuration(
                context.get("ads_configuration") or None
            )
            period_configuration = ads_period_configuration(
                payload or {},
                product_configuration["platforms"],
            )
            saved = conn.execute(
                text(
                    """
                    UPDATE meta_ads_report_periods
                    SET configuration = CAST(:configuration AS JSONB),
                        updated_at = now()
                    WHERE id = CAST(:period_id AS UUID)
                      AND client_id = CAST(:client_id AS UUID)
                    RETURNING id, period_label
                    """
                ),
                {
                    "client_id": client_id,
                    "period_id": period_id,
                    "configuration": _json(period_configuration),
                },
            ).mappings().one()
            return {
                "period_id": saved["id"],
                "period_label": saved["period_label"],
                "ads_configuration": period_configuration,
                "goals": period_configuration["goals"],
                "platform_catalog": ads_platform_catalog(
                    product_configuration,
                    period_configuration,
                ),
            }

    def delete_period(self, client_id: str, period_id: str) -> dict:
        UUID(client_id)
        UUID(period_id)
        with self.engine.begin() as conn:
            period = conn.execute(
                text(
                    """
                    DELETE FROM meta_ads_report_periods
                    WHERE id = CAST(:period_id AS UUID)
                      AND client_id = CAST(:client_id AS UUID)
                    RETURNING id, period_label
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
            if not period:
                raise ValueError("Ads report period was not found.")
            return {
                "deleted": True,
                "period_id": period["id"],
                "period_label": period["period_label"],
            }

    @staticmethod
    def _insert_rows(
        conn,
        *,
        file_type: str,
        import_id,
        client_id: str,
        period_id,
        rows,
    ) -> int:
        fields = TABLE_FIELDS[file_type]
        columns = (
            "import_id",
            "client_id",
            "meta_ads_report_period_id",
            *fields,
            "raw_data",
        )
        bind_names = ", ".join(f":{column}" for column in columns)
        statement = text(
            f"INSERT INTO {TABLES[file_type]} ({', '.join(columns)}) VALUES ({bind_names})"
        )
        parameters = []
        for row in rows:
            item = {
                "import_id": import_id,
                "client_id": client_id,
                "meta_ads_report_period_id": period_id,
                **{field: row.get(field) for field in fields},
                "raw_data": _json(row.get("raw_data") or {}),
            }
            parameters.append(item)
        if parameters:
            # raw_data is explicitly cast in SQL because psycopg otherwise sees
            # a plain string. Keep the rest as typed bind parameters.
            raw_statement = str(statement).replace(":raw_data", "CAST(:raw_data AS JSONB)")
            conn.execute(text(raw_statement), parameters)
        return len(parameters)
