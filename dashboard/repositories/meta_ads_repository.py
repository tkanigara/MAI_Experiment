from __future__ import annotations

import json
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text

try:
    from dashboard.db import create_db_engine
    from dashboard.services.ads_workspace import (
        ADS_GOAL_DEFINITIONS,
        LEGACY_ADS_GOAL_DEFINITIONS,
        ADS_PLATFORM_KEYS,
        ads_period_configuration,
        ads_platform_catalog,
        ads_product_configuration,
    )
    from dashboard.services.ads_objectives import (
        METRICS,
        OBJECTIVE_CATALOG,
        normalize_metric_keys,
        objective_catalog,
        objective_definition,
        result_metric_for_objective,
        suggest_meta_objective,
    )
except ModuleNotFoundError:
    from db import create_db_engine
    from services.ads_workspace import (
        ADS_GOAL_DEFINITIONS,
        LEGACY_ADS_GOAL_DEFINITIONS,
        ADS_PLATFORM_KEYS,
        ads_period_configuration,
        ads_platform_catalog,
        ads_product_configuration,
    )
    from services.ads_objectives import (
        METRICS,
        OBJECTIVE_CATALOG,
        normalize_metric_keys,
        objective_catalog,
        objective_definition,
        result_metric_for_objective,
        suggest_meta_objective,
    )


TABLES = {
    "campaign": "meta_ads_campaign_performance",
    "adset": "meta_ads_adset_performance",
    "ad": "meta_ads_ad_performance",
    "placement": "meta_ads_placement_breakdown",
    "demographic": "meta_ads_demographic_breakdown",
    "region": "meta_ads_region_breakdown",
}

ADS_EDITOR_METRICS = (
    "result_value", "reach", "impressions", "post_engagements", "interactions",
    "post_shares", "post_saves", "post_reactions", "post_comments", "link_clicks",
    "destination_clicks", "spend", "video_views", "thruplay", "leads",
    "profile_visits", "page_likes",
)

ADS_EDITOR_DEFINITIONS = {
    "campaign": {"label": "Campaigns", "name_field": "campaign_name", "fields": ("campaign_name", *ADS_EDITOR_METRICS)},
    "adset": {"label": "Ad Sets", "name_field": "adset_name", "fields": ("adset_name", *ADS_EDITOR_METRICS)},
    "ad": {"label": "Ads / Creatives", "name_field": "ad_name", "fields": ("ad_name", *ADS_EDITOR_METRICS)},
    "placement": {"label": "Placements", "name_field": "ad_name", "fields": ADS_EDITOR_METRICS},
}

META_GOAL_RESULT_TYPES = {
    "reach": ("reach",),
    "engagement": ("actions:post_interaction_gross", "post_engagement"),
    "views": ("video_view",),
    "link_clicks": ("link_click",),
    "leads": ("lead",),
    "profile_visits": ("profile_visit_view", "profile_visit"),
    "page_likes": (
        "page_like",
        "page_likes",
        "actions:page_like",
        "profile_visit_view",
        "profile_visit",
    ),
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
    "campaign_objective",
    "optimization_goal",
    "interactions",
    "post_shares",
    "post_saves",
    "post_reactions",
    "post_comments",
    "video_views",
    "thruplay",
    "leads",
    "destination_clicks",
    "profile_visits",
    "page_likes",
)

TABLE_FIELDS = {
    "campaign": (
        "meta_ad_account_id",
        "campaign_external_id",
        "campaign_name",
        *COMMON_FIELDS,
    ),
    "adset": (
        "meta_ad_account_id",
        "campaign_performance_id",
        "campaign_external_id",
        "campaign_name",
        "adset_external_id",
        "adset_name",
        *COMMON_FIELDS,
    ),
    "ad": (
        "meta_ad_account_id",
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
        "meta_ad_account_id",
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
        "meta_ad_account_id",
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
        "meta_ad_account_id",
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
                        diagnostics, warnings, imported_at, schema_version,
                        date_preset, data_start, data_end
                    )
                    VALUES (
                        CAST(:client_id AS UUID), :period_id, 'meta',
                        'csv', 'running', CAST(:filenames AS JSONB),
                        CAST(:summary_totals AS JSONB),
                        CAST(:diagnostics AS JSONB), CAST(:warnings AS JSONB), now(), 2,
                        'csv_export', :data_start, :data_end
                    )
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
                    "data_start": period_start,
                    "data_end": period_end,
                },
            ).scalar_one()

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
                    SET status = 'success',
                        platform_scope = '["instagram", "facebook"]'::jsonb,
                        row_counts = CAST(:counts AS JSONB),
                        sync_completed_at = now(), updated_at = now()
                    WHERE id = :import_id
                    """
                ),
                {"import_id": import_id, "counts": _json(counts)},
            )
            for platform in ("instagram", "facebook"):
                self._activate_snapshot(conn, period_id, platform, import_id)
            self._refresh_campaign_mappings(
                conn,
                client_id=client_id,
                period_id=period_id,
                campaigns=files["campaign"].rows,
            )

        return {
            "import_id": import_id,
            "meta_ads_report_period_id": period_id,
            "counts": counts,
        }

    @staticmethod
    def _activate_snapshot(conn, period_id, platform: str, import_id) -> None:
        conn.execute(
            text(
                """
                INSERT INTO meta_ads_active_snapshots (meta_ads_report_period_id, platform, import_id)
                VALUES (:period_id, :platform, :import_id)
                ON CONFLICT (meta_ads_report_period_id, platform)
                DO UPDATE SET import_id = EXCLUDED.import_id, selected_at = now()
                """
            ),
            {"period_id": period_id, "platform": platform, "import_id": import_id},
        )

    def create_period(self, client_id: str, payload: dict) -> dict:
        UUID(client_id)
        try:
            period_start = date.fromisoformat(str(payload.get("period_start") or ""))
            period_end = date.fromisoformat(str(payload.get("period_end") or ""))
        except ValueError as exc:
            raise ValueError("A valid period_start and period_end are required.") from exc
        if period_end < period_start:
            raise ValueError("Period end cannot be before period start.")
        period_start = period_start.replace(day=1)
        period_end = period_start.replace(day=calendar.monthrange(period_start.year, period_start.month)[1])
        with self.engine.begin() as conn:
            product = conn.execute(
                text("SELECT configuration FROM client_products WHERE client_id=CAST(:client_id AS UUID) AND product='meta_ads' AND is_active"),
                {"client_id": client_id},
            ).mappings().first()
            if not product:
                raise ValueError("Ads client was not found.")
            configuration = ads_product_configuration(product.get("configuration") or None)
            has_goal_configuration = "goals" in payload or "ads_goals" in payload
            period_configuration = ads_period_configuration(
                payload if has_goal_configuration else None,
                configuration["platforms"],
            )
            existing = conn.execute(text("""
                SELECT id, period_start, period_end, period_label, configuration
                FROM meta_ads_report_periods
                WHERE client_id=CAST(:client_id AS UUID)
                  AND DATE_TRUNC('month', period_start)=DATE_TRUNC('month', CAST(:period_start AS DATE))
                ORDER BY created_at LIMIT 1
            """), {"client_id": client_id, "period_start": period_start}).mappings().first()
            if existing:
                result = dict(existing)
                existing_configuration = result.pop("configuration", None)
                return {**result, "ads_configuration": existing_configuration or period_configuration, "already_exists": True}
            row = conn.execute(
                text(
                    """
                    INSERT INTO meta_ads_report_periods (client_id, period_start, period_end, period_label, configuration)
                    VALUES (CAST(:client_id AS UUID), :period_start, :period_end,
                            to_char(CAST(:period_start AS DATE), 'FMMonth YYYY'), CAST(:configuration AS JSONB))
                    ON CONFLICT (client_id, period_start, period_end) DO NOTHING
                    RETURNING id, period_start, period_end, period_label, configuration
                    """
                ),
                {"client_id": client_id, "period_start": period_start, "period_end": period_end, "configuration": _json(period_configuration)},
            ).mappings().first()
            already_exists = row is None
            if already_exists:
                row = conn.execute(
                    text(
                        """
                        SELECT id, period_start, period_end, period_label, configuration
                        FROM meta_ads_report_periods
                        WHERE client_id=CAST(:client_id AS UUID)
                          AND period_start=:period_start AND period_end=:period_end
                        """
                    ),
                    {"client_id": client_id, "period_start": period_start, "period_end": period_end},
                ).mappings().one()
            result = dict(row)
            existing_configuration = result.pop("configuration", None)
            return {
                **result,
                "ads_configuration": existing_configuration or period_configuration,
                "already_exists": already_exists,
            }

    def sync_context(self, client_id: str, period_id: str, account_ids: list[str], goals=None) -> dict:
        UUID(client_id); UUID(period_id)
        with self.engine.begin() as conn:
            period = conn.execute(
                text(
                    """
                    SELECT p.period_start, p.period_end, p.configuration, cp.configuration AS product_configuration
                    FROM meta_ads_report_periods p JOIN client_products cp ON cp.client_id=p.client_id
                    WHERE p.id=CAST(:period_id AS UUID) AND p.client_id=CAST(:client_id AS UUID)
                      AND cp.product='meta_ads' AND cp.is_active FOR UPDATE OF p
                    """
                ), {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
            if not period:
                raise ValueError("Ads report period was not found.")
            rows = conn.execute(
                text(
                    """
                    SELECT ad_account_id AS id, account_name AS name, account_status, currency, timezone_name, is_active
                    FROM client_meta_ad_accounts
                    WHERE client_id=CAST(:client_id AS UUID) AND ad_account_id = ANY(CAST(:account_ids AS TEXT[]))
                    """
                ), {"client_id": client_id, "account_ids": account_ids},
            ).mappings().all()
            found = {row["id"] for row in rows}
            if found != set(account_ids):
                raise ValueError("One or more Ad Accounts are not connected to this client.")
            if any(not row["is_active"] or row["account_status"] != 1 for row in rows):
                raise ValueError("Inactive Meta Ad Accounts cannot be synced.")
            product_configuration = ads_product_configuration(period.get("product_configuration") or None)
            period_configuration = ads_period_configuration({"goals": goals} if goals else period.get("configuration"), product_configuration["platforms"])
            if goals:
                conn.execute(text("UPDATE meta_ads_report_periods SET configuration=CAST(:configuration AS JSONB), updated_at=now() WHERE id=CAST(:period_id AS UUID)"), {"period_id": period_id, "configuration": _json(period_configuration)})
            return {"period_start": period["period_start"], "period_end": period["period_end"], "accounts": [dict(row) for row in rows], "goals": period_configuration["goals"]}

    @staticmethod
    def resolve_sync_range(period_start: date, date_range: dict | None = None) -> dict:
        request = date_range or {}
        preset = str(request.get("preset") or "month_to_date").lower()
        allowed = {"month_to_date", "last_7_days", "full_month", "custom"}
        if preset not in allowed:
            raise ValueError("Choose Month to date, Last 7 days, Full month, or Custom range.")
        month_start = period_start.replace(day=1)
        month_end = period_start.replace(day=calendar.monthrange(period_start.year, period_start.month)[1])
        today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
        if month_start > today:
            raise ValueError("A future report month cannot be synced yet.")
        if preset == "month_to_date":
            data_start, data_end = month_start, min(today, month_end)
        elif preset == "last_7_days":
            data_end = min(today, month_end)
            data_start = max(month_start, data_end - timedelta(days=6))
        elif preset == "full_month":
            if month_end > today:
                raise ValueError("Full month is available after the month has ended. Use Month to date for the current month.")
            data_start, data_end = month_start, month_end
        else:
            try:
                data_start = date.fromisoformat(str(request.get("start") or ""))
                data_end = date.fromisoformat(str(request.get("end") or ""))
            except ValueError as exc:
                raise ValueError("Choose valid start and end dates for the custom range.") from exc
            if data_end < data_start:
                raise ValueError("Custom range end cannot be before its start.")
            if data_start < month_start or data_end > month_end:
                raise ValueError("Custom range must stay within the selected report month.")
            if data_end > today:
                raise ValueError("Custom range cannot end in the future.")
        return {"preset": preset, "start": data_start, "end": data_end}

    def start_api_snapshot(self, client_id, period_id, account_ids, platforms, warnings, sync_range=None) -> str:
        sync_range = sync_range or {}
        with self.engine.begin() as conn:
            return str(conn.execute(
                text(
                    """
                    INSERT INTO meta_ads_imports (client_id, meta_ads_report_period_id, platform, source, status,
                      selected_ad_account_ids, platform_scope, warnings, sync_started_at, imported_at, schema_version,
                      date_preset, data_start, data_end)
                    VALUES (CAST(:client_id AS UUID), CAST(:period_id AS UUID), 'meta', 'api', 'running',
                      CAST(:accounts AS JSONB), CAST(:platforms AS JSONB), CAST(:warnings AS JSONB), now(), now(), 2,
                      :date_preset, :data_start, :data_end) RETURNING id
                    """
                ), {"client_id": client_id, "period_id": period_id, "accounts": _json(account_ids), "platforms": _json(platforms), "warnings": _json(warnings),
                    "date_preset": sync_range.get("preset"), "data_start": sync_range.get("start"), "data_end": sync_range.get("end")},
            ).scalar_one())

    def complete_api_snapshot(self, import_id, client_id, period_id, platforms, datasets, creatives, warnings) -> dict:
        UUID(str(import_id))
        with self.engine.begin() as conn:
            counts = {}
            for file_type, rows in datasets.items():
                counts[file_type] = self._insert_rows(conn, file_type=file_type, import_id=import_id, client_id=client_id, period_id=period_id, rows=rows)
            if creatives:
                fields = ("meta_ad_account_id", "campaign_external_id", "adset_external_id", "ad_external_id", "creative_external_id", "creative_name", "thumbnail_url", "image_url", "preview_url", "permalink_url", "effective_object_story_id", "page_id", "instagram_actor_id", "creative_fetched_at")
                statement = text(f"INSERT INTO meta_ads_creatives (import_id, client_id, meta_ads_report_period_id, {', '.join(fields)}, raw_data) VALUES (:import_id, CAST(:client_id AS UUID), CAST(:period_id AS UUID), {', '.join(':'+f for f in fields)}, CAST(:raw_data AS JSONB))")
                conn.execute(statement, [{"import_id": import_id, "client_id": client_id, "period_id": period_id, **{field: item.get(field) for field in fields}, "raw_data": _json(item.get("raw_data") or {})} for item in creatives])
            conn.execute(text("UPDATE meta_ads_imports SET status='success', row_counts=CAST(:counts AS JSONB), warnings=CAST(:warnings AS JSONB), sync_completed_at=now(), updated_at=now() WHERE id=CAST(:import_id AS UUID)"), {"import_id": import_id, "counts": _json({**counts, "creatives": len(creatives)}), "warnings": _json(warnings)})
            for platform in platforms:
                self._activate_snapshot(conn, period_id, platform, import_id)
            self._refresh_campaign_mappings(
                conn,
                client_id=client_id,
                period_id=period_id,
                campaigns=datasets.get("campaign") or [],
            )
        return {"import_id": import_id, "meta_ads_report_period_id": period_id, "platforms": platforms, "counts": {**counts, "creatives": len(creatives)}, "warnings": warnings, "status": "success"}

    @staticmethod
    def _refresh_campaign_mappings(conn, *, client_id: str, period_id, campaigns) -> None:
        grouped = {}
        for row in campaigns:
            name = str(row.get("campaign_name") or "Unnamed campaign").strip()
            external_id = str(row.get("campaign_external_id") or "").strip() or None
            account_id = str(row.get("meta_ad_account_id") or "").strip()
            campaign_key = external_id or f"csv:{name.casefold()}"
            item = grouped.setdefault((account_id, campaign_key), {
                "account_id": account_id,
                "external_id": external_id,
                "campaign_key": campaign_key,
                "campaign_name": name,
                "detected_objective": row.get("campaign_objective") or (row.get("raw_data") or {}).get("campaign_objective"),
                "optimization_goals": set(),
                "result_types": set(),
            })
            optimization = row.get("optimization_goal") or (row.get("raw_data") or {}).get("optimization_goal")
            if optimization:
                item["optimization_goals"].add(str(optimization))
            if row.get("result_type"):
                item["result_types"].add(str(row["result_type"]))
        for item in grouped.values():
            optimization_goals = sorted(item["optimization_goals"])
            result_types = sorted(item["result_types"])
            suggestion = suggest_meta_objective(item["detected_objective"], optimization_goals, result_types)
            params = {
                "client_id": client_id,
                "period_id": period_id,
                "account_id": item["account_id"],
                "external_id": item["external_id"],
                "campaign_key": item["campaign_key"],
                "campaign_name": item["campaign_name"],
                "detected_objective": item["detected_objective"],
                "optimization_goals": _json(optimization_goals),
                "result_types": _json(result_types),
                "suggested_objective": suggestion["objective"],
                "confidence": suggestion["confidence"],
            }
            if item["external_id"]:
                conn.execute(text("""
                    INSERT INTO meta_ads_campaign_objective_mappings (
                        client_id, meta_ad_account_id, campaign_external_id, campaign_key,
                        campaign_name, detected_objective, optimization_goals, result_types,
                        suggested_objective, suggestion_confidence
                    ) VALUES (
                        CAST(:client_id AS UUID), :account_id, :external_id, :campaign_key,
                        :campaign_name, :detected_objective, CAST(:optimization_goals AS JSONB),
                        CAST(:result_types AS JSONB), :suggested_objective, :confidence
                    )
                    ON CONFLICT (client_id, meta_ad_account_id, campaign_external_id)
                    WHERE campaign_external_id IS NOT NULL DO UPDATE SET
                        campaign_name=EXCLUDED.campaign_name,
                        detected_objective=EXCLUDED.detected_objective,
                        optimization_goals=EXCLUDED.optimization_goals,
                        result_types=EXCLUDED.result_types,
                        suggested_objective=EXCLUDED.suggested_objective,
                        suggestion_confidence=EXCLUDED.suggestion_confidence,
                        updated_at=now()
                """), params)
            else:
                conn.execute(text("""
                    INSERT INTO meta_ads_campaign_objective_mappings (
                        client_id, meta_ads_report_period_id, meta_ad_account_id, campaign_key,
                        campaign_name, detected_objective, optimization_goals, result_types,
                        suggested_objective, suggestion_confidence
                    ) VALUES (
                        CAST(:client_id AS UUID), CAST(:period_id AS UUID), :account_id, :campaign_key,
                        :campaign_name, :detected_objective, CAST(:optimization_goals AS JSONB),
                        CAST(:result_types AS JSONB), :suggested_objective, :confidence
                    )
                    ON CONFLICT (meta_ads_report_period_id, campaign_key)
                    WHERE campaign_external_id IS NULL DO UPDATE SET
                        campaign_name=EXCLUDED.campaign_name,
                        detected_objective=EXCLUDED.detected_objective,
                        optimization_goals=EXCLUDED.optimization_goals,
                        result_types=EXCLUDED.result_types,
                        suggested_objective=EXCLUDED.suggested_objective,
                        suggestion_confidence=EXCLUDED.suggestion_confidence,
                        updated_at=now()
                """), params)

    def fail_api_snapshot(self, import_id, error_message: str) -> None:
        safe_error = str(error_message).replace("META_ADS_ACCESS_TOKEN=", "")[:1000]
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE meta_ads_imports SET status='failed', error_message=:error, sync_completed_at=now(), updated_at=now() WHERE id=CAST(:import_id AS UUID)"), {"import_id": import_id, "error": safe_error})

    def sources(self, client_id: str, period_id: str) -> dict:
        UUID(client_id); UUID(period_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT i.id, i.source, i.status, i.selected_ad_account_ids, i.platform_scope, i.row_counts,
                       i.date_preset, i.data_start, i.data_end,
                       i.warnings, i.error_message, i.imported_at, i.sync_completed_at,
                       ARRAY_REMOVE(ARRAY_AGG(a.platform), NULL) AS active_for
                FROM meta_ads_imports i LEFT JOIN meta_ads_active_snapshots a ON a.import_id=i.id
                WHERE i.client_id=CAST(:client_id AS UUID) AND i.meta_ads_report_period_id=CAST(:period_id AS UUID)
                GROUP BY i.id ORDER BY COALESCE(i.sync_completed_at, i.imported_at, i.created_at) DESC
            """), {"client_id": client_id, "period_id": period_id}).mappings().all()
            return {"snapshots": [dict(row) for row in rows]}

    def metric_configurations(self, client_id: str) -> dict:
        UUID(client_id)
        with self.engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM client_products WHERE client_id=CAST(:client_id AS UUID) AND product='meta_ads' AND is_active"),
                {"client_id": client_id},
            ).first()
            if not exists:
                raise ValueError("Ads client was not found.")
            stored = conn.execute(
                text("SELECT scope, objective_key, metric_keys, updated_at FROM ads_metric_configurations WHERE client_id=CAST(:client_id AS UUID)"),
                {"client_id": client_id},
            ).mappings().all()
        overrides = {(row["scope"], row["objective_key"]): row for row in stored}
        configurations = []
        for scope_key, scope in OBJECTIVE_CATALOG.items():
            for objective in scope["objectives"]:
                override = overrides.get((scope_key, objective["key"]))
                configurations.append({
                    "scope": scope_key,
                    "scope_label": scope["label"],
                    "available": scope["available"],
                    "objective": objective["key"],
                    "objective_label": objective["label"],
                    "metric_keys": list(override["metric_keys"]) if override else list(objective["default_metric_keys"]),
                    "default_metric_keys": list(objective["default_metric_keys"]),
                    "available_metrics": [{"key": key, **METRICS[key]} for key in objective["metric_keys"]],
                    "customized": override is not None,
                    "updated_at": override["updated_at"] if override else None,
                })
        return {"configurations": configurations}

    def save_metric_configuration(self, client_id: str, scope: str, objective: str, payload: dict) -> dict:
        UUID(client_id)
        scope = str(scope or "").lower()
        objective = str(objective or "").lower()
        metric_keys = normalize_metric_keys(scope, objective, payload.get("metric_keys"))
        with self.engine.begin() as conn:
            row = conn.execute(text("""
                INSERT INTO ads_metric_configurations (client_id, scope, objective_key, metric_keys)
                SELECT CAST(:client_id AS UUID), :scope, :objective, CAST(:metric_keys AS JSONB)
                WHERE EXISTS (
                    SELECT 1 FROM client_products
                    WHERE client_id=CAST(:client_id AS UUID) AND product='meta_ads' AND is_active
                )
                ON CONFLICT (client_id, scope, objective_key) DO UPDATE SET
                    metric_keys=EXCLUDED.metric_keys, updated_at=now()
                RETURNING scope, objective_key, metric_keys, updated_at
            """), {"client_id": client_id, "scope": scope, "objective": objective, "metric_keys": _json(metric_keys)}).mappings().first()
            if not row:
                raise ValueError("Ads client was not found.")
        definition = objective_definition(scope, objective)
        return {**dict(row), "metric_keys": list(row["metric_keys"]), "default_metric_keys": list(definition["default_metric_keys"]), "customized": True}

    def reset_metric_configuration(self, client_id: str, scope: str, objective: str) -> dict:
        UUID(client_id)
        scope = str(scope or "").lower()
        objective = str(objective or "").lower()
        definition = objective_definition(scope, objective)
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM ads_metric_configurations WHERE client_id=CAST(:client_id AS UUID) AND scope=:scope AND objective_key=:objective"),
                {"client_id": client_id, "scope": scope, "objective": objective},
            )
        return {"scope": scope, "objective_key": objective, "metric_keys": list(definition["default_metric_keys"]), "customized": False}

    @staticmethod
    def _editor_value(field: str, value):
        if field not in ADS_EDITOR_METRICS:
            value = str(value or "").strip()
            if not value:
                raise ValueError("Names cannot be empty.")
            return value
        if value is None or str(value).strip() == "":
            return None
        try:
            number = Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            raise ValueError(f"{field.replace('_', ' ').title()} must be a number.")
        if number < 0:
            raise ValueError(f"{field.replace('_', ' ').title()} cannot be negative.")
        return float(number)

    @staticmethod
    def _apply_data_overrides(conn, import_id, entity_type: str, rows) -> list[dict]:
        result = [dict(row) for row in rows]
        row_ids = [str(row.get("row_id")) for row in result if row.get("row_id")]
        if not row_ids:
            return result
        overrides = conn.execute(text("""
            SELECT entity_row_id, field_key, override_value
            FROM meta_ads_data_overrides
            WHERE import_id=CAST(:import_id AS UUID) AND entity_type=:entity_type
              AND is_active AND entity_row_id = ANY(CAST(:row_ids AS UUID[]))
        """), {"import_id": import_id, "entity_type": entity_type, "row_ids": row_ids}).mappings().all()
        by_row = {}
        for override in overrides:
            by_row.setdefault(str(override["entity_row_id"]), {})[override["field_key"]] = override["override_value"]
        for row in result:
            row.update(by_row.get(str(row.get("row_id")), {}))
        return result

    def data_editor(self, client_id: str, period_id: str) -> dict:
        UUID(client_id); UUID(period_id)
        with self.engine.connect() as conn:
            period = conn.execute(text("""
                SELECT p.id, p.period_label, p.period_start, p.period_end
                FROM meta_ads_report_periods p
                WHERE p.id=CAST(:period_id AS UUID) AND p.client_id=CAST(:client_id AS UUID)
            """), {"client_id": client_id, "period_id": period_id}).mappings().first()
            if not period:
                raise ValueError("Ads reporting period was not found.")
            snapshots = conn.execute(text("""
                SELECT active.platform, i.id AS import_id, i.source, i.imported_at,
                    i.sync_completed_at, i.selected_ad_account_ids, i.date_preset, i.data_start, i.data_end
                FROM meta_ads_active_snapshots active
                JOIN meta_ads_imports i ON i.id=active.import_id
                WHERE active.meta_ads_report_period_id=CAST(:period_id AS UUID)
                  AND i.client_id=CAST(:client_id AS UUID) AND i.status='success'
                ORDER BY active.platform
            """), {"client_id": client_id, "period_id": period_id}).mappings().all()
            import_ids = list(dict.fromkeys(str(row["import_id"]) for row in snapshots))
            sections = {}
            for entity_type, definition in ADS_EDITOR_DEFINITIONS.items():
                table = TABLES[entity_type]
                if not import_ids:
                    sections[entity_type] = []
                    continue
                identity = {
                    "campaign": "campaign_external_id, campaign_name, NULL::TEXT AS adset_external_id, NULL::TEXT AS adset_name, NULL::TEXT AS ad_external_id, NULL::TEXT AS ad_name, NULL::TEXT AS publisher_platform, NULL::TEXT AS placement, NULL::TEXT AS device_platform",
                    "adset": "campaign_external_id, campaign_name, adset_external_id, adset_name, NULL::TEXT AS ad_external_id, NULL::TEXT AS ad_name, NULL::TEXT AS publisher_platform, NULL::TEXT AS placement, NULL::TEXT AS device_platform",
                    "ad": "campaign_external_id, campaign_name, adset_external_id, adset_name, ad_external_id, ad_name, NULL::TEXT AS publisher_platform, NULL::TEXT AS placement, NULL::TEXT AS device_platform",
                    "placement": "campaign_external_id, campaign_name, adset_external_id, adset_name, ad_external_id, ad_name, publisher_platform, placement, device_platform",
                }[entity_type]
                fields = ", ".join(definition["fields"])
                rows = conn.execute(text(f"""
                    SELECT id AS row_id, import_id, meta_ad_account_id, {identity}, {fields}
                    FROM {table}
                    WHERE client_id=CAST(:client_id AS UUID)
                      AND meta_ads_report_period_id=CAST(:period_id AS UUID)
                      AND import_id = ANY(CAST(:import_ids AS UUID[]))
                    ORDER BY campaign_name NULLS LAST, adset_name NULLS LAST, ad_name NULLS LAST, source_row_number
                    LIMIT 2000
                """), {"client_id": client_id, "period_id": period_id, "import_ids": import_ids}).mappings().all()
                rows = [dict(row) for row in rows]
                overrides = conn.execute(text("""
                    SELECT id, import_id, entity_row_id, field_key, override_value,
                        source_value, version, edited_by, updated_at
                    FROM meta_ads_data_overrides
                    WHERE meta_ads_report_period_id=CAST(:period_id AS UUID)
                      AND client_id=CAST(:client_id AS UUID) AND entity_type=:entity_type AND is_active
                """), {"client_id": client_id, "period_id": period_id, "entity_type": entity_type}).mappings().all()
                by_row = {}
                for override in overrides:
                    by_row.setdefault(str(override["entity_row_id"]), {})[override["field_key"]] = dict(override)
                rendered = []
                for row in rows:
                    original = {field: row.get(field) for field in definition["fields"]}
                    row_overrides = by_row.get(str(row["row_id"]), {})
                    effective = dict(original)
                    effective.update({field: item["override_value"] for field, item in row_overrides.items()})
                    rendered.append({
                        **{key: value for key, value in row.items() if key not in definition["fields"]},
                        "label": effective.get(definition["name_field"]) or row.get("ad_name") or row.get("adset_name") or row.get("campaign_name") or "Unnamed row",
                        "source_values": original, "values": effective,
                        "overrides": row_overrides,
                    })
                sections[entity_type] = rendered
            history = conn.execute(text("""
                SELECT id, entity_type, entity_label, field_key, action, old_value,
                    new_value, edited_by, created_at
                FROM meta_ads_data_edit_history
                WHERE client_id=CAST(:client_id AS UUID)
                  AND meta_ads_report_period_id=CAST(:period_id AS UUID)
                ORDER BY created_at DESC LIMIT 100
            """), {"client_id": client_id, "period_id": period_id}).mappings().all()
        return {
            "period": dict(period), "snapshots": [dict(row) for row in snapshots],
            "definitions": {key: {**value, "fields": list(value["fields"])} for key, value in ADS_EDITOR_DEFINITIONS.items()},
            "metric_definitions": {key: METRICS.get(key, {"label": key.replace("_", " ").title(), "format": "number"}) for key in ADS_EDITOR_METRICS},
            "sections": sections, "history": [dict(row) for row in history],
        }

    def save_data_editor(self, client_id: str, period_id: str, entity_type: str, payload: dict) -> dict:
        UUID(client_id); UUID(period_id)
        entity_type = str(entity_type or "").lower()
        definition = ADS_EDITOR_DEFINITIONS.get(entity_type)
        if not definition:
            raise ValueError("Unsupported Ads editor section.")
        actor = str(payload.get("actor") or "").strip()
        if len(actor) < 2:
            raise ValueError("Enter your editor name before saving.")
        changes = payload.get("changes")
        if not isinstance(changes, list) or not changes:
            raise ValueError("No changes were provided.")
        table = TABLES[entity_type]
        with self.engine.begin() as conn:
            active_ids = {str(value) for value in conn.execute(text("""
                SELECT DISTINCT active.import_id FROM meta_ads_active_snapshots active
                JOIN meta_ads_imports i ON i.id=active.import_id
                WHERE active.meta_ads_report_period_id=CAST(:period_id AS UUID)
                  AND i.client_id=CAST(:client_id AS UUID) AND i.status='success'
            """), {"client_id": client_id, "period_id": period_id}).scalars().all()}
            for change in changes:
                row_id = str(change.get("row_id") or "")
                field = str(change.get("field") or "")
                UUID(row_id)
                if field not in definition["fields"]:
                    raise ValueError("This field cannot be edited.")
                row = conn.execute(text(f"""
                    SELECT id, import_id, {definition['name_field']} AS entity_label, {field} AS source_value
                    FROM {table}
                    WHERE id=CAST(:row_id AS UUID) AND client_id=CAST(:client_id AS UUID)
                      AND meta_ads_report_period_id=CAST(:period_id AS UUID)
                """), {"row_id": row_id, "client_id": client_id, "period_id": period_id}).mappings().first()
                if not row or str(row["import_id"]) not in active_ids:
                    raise ValueError("The row is not part of an active Ads snapshot.")
                value = self._editor_value(field, change.get("value"))
                existing = conn.execute(text("""
                    SELECT * FROM meta_ads_data_overrides
                    WHERE import_id=:import_id AND entity_type=:entity_type
                      AND entity_row_id=CAST(:row_id AS UUID) AND field_key=:field
                    FOR UPDATE
                """), {"import_id": row["import_id"], "entity_type": entity_type, "row_id": row_id, "field": field}).mappings().first()
                expected_version = change.get("version")
                if existing and expected_version is not None and int(expected_version) != int(existing["version"]):
                    raise RuntimeError("VERSION_CONFLICT: Ads data changed after this page was loaded. Refresh and try again.")
                old_value = existing["override_value"] if existing and existing["is_active"] else row["source_value"]
                saved = conn.execute(text("""
                    INSERT INTO meta_ads_data_overrides (
                        client_id, meta_ads_report_period_id, import_id, entity_type,
                        entity_row_id, field_key, source_value, override_value, edited_by
                    ) VALUES (
                        CAST(:client_id AS UUID), CAST(:period_id AS UUID), :import_id, :entity_type,
                        CAST(:row_id AS UUID), :field, CAST(:source AS JSONB), CAST(:value AS JSONB), :actor
                    ) ON CONFLICT (import_id, entity_type, entity_row_id, field_key) DO UPDATE SET
                        override_value=EXCLUDED.override_value, is_active=TRUE, edited_by=EXCLUDED.edited_by,
                        version=meta_ads_data_overrides.version + 1, updated_at=now()
                    RETURNING id
                """), {
                    "client_id": client_id, "period_id": period_id, "import_id": row["import_id"],
                    "entity_type": entity_type, "row_id": row_id, "field": field,
                    "source": _json(row["source_value"]), "value": _json(value), "actor": actor,
                }).scalar_one()
                conn.execute(text("""
                    INSERT INTO meta_ads_data_edit_history (
                        override_id, client_id, meta_ads_report_period_id, import_id,
                        entity_type, entity_row_id, entity_label, field_key, action,
                        old_value, new_value, edited_by
                    ) VALUES (
                        :override_id, CAST(:client_id AS UUID), CAST(:period_id AS UUID), :import_id,
                        :entity_type, CAST(:row_id AS UUID), :label, :field, 'update',
                        CAST(:old AS JSONB), CAST(:new AS JSONB), :actor
                    )
                """), {
                    "override_id": saved, "client_id": client_id, "period_id": period_id,
                    "import_id": row["import_id"], "entity_type": entity_type, "row_id": row_id,
                    "label": row["entity_label"], "field": field, "old": _json(old_value),
                    "new": _json(value), "actor": actor,
                })
        return self.data_editor(client_id, period_id)

    def restore_data_override(self, client_id: str, period_id: str, override_id: str, actor: str) -> dict:
        UUID(client_id); UUID(period_id); UUID(override_id)
        actor = str(actor or "").strip()
        if len(actor) < 2:
            raise ValueError("Enter your editor name before restoring.")
        with self.engine.begin() as conn:
            row = conn.execute(text("""
                SELECT * FROM meta_ads_data_overrides
                WHERE id=CAST(:override_id AS UUID) AND client_id=CAST(:client_id AS UUID)
                  AND meta_ads_report_period_id=CAST(:period_id AS UUID) FOR UPDATE
            """), {"override_id": override_id, "client_id": client_id, "period_id": period_id}).mappings().first()
            if not row:
                raise ValueError("Ads data override was not found.")
            conn.execute(text("""
                UPDATE meta_ads_data_overrides SET is_active=FALSE, edited_by=:actor,
                    version=version+1, updated_at=now() WHERE id=CAST(:override_id AS UUID)
            """), {"override_id": override_id, "actor": actor})
            conn.execute(text("""
                INSERT INTO meta_ads_data_edit_history (
                    override_id, client_id, meta_ads_report_period_id, import_id, entity_type,
                    entity_row_id, field_key, action, old_value, new_value, edited_by
                ) VALUES (
                    CAST(:override_id AS UUID), CAST(:client_id AS UUID), CAST(:period_id AS UUID),
                    :import_id, :entity_type, :entity_row_id, :field, 'restore',
                    CAST(:old AS JSONB), CAST(:new AS JSONB), :actor
                )
            """), {"override_id": override_id, "client_id": client_id, "period_id": period_id,
                "import_id": row["import_id"], "entity_type": row["entity_type"], "entity_row_id": row["entity_row_id"],
                "field": row["field_key"], "old": _json(row["override_value"]), "new": _json(row["source_value"]), "actor": actor})
        return self.data_editor(client_id, period_id)

    def campaign_mappings(self, client_id: str, period_id: str) -> dict:
        UUID(client_id); UUID(period_id)
        with self.engine.connect() as conn:
            import_id = conn.execute(text("""
                SELECT active.import_id
                FROM meta_ads_active_snapshots active
                JOIN meta_ads_imports i ON i.id=active.import_id
                WHERE active.meta_ads_report_period_id=CAST(:period_id AS UUID) AND i.client_id=CAST(:client_id AS UUID)
                ORDER BY active.selected_at DESC LIMIT 1
            """), {"client_id": client_id, "period_id": period_id}).scalar()
            if not import_id:
                return {"campaigns": [], "unconfirmed_count": 0}
            rows = conn.execute(text("""
                SELECT DISTINCT ON (COALESCE(meta_ad_account_id, ''), COALESCE(campaign_external_id, campaign_name))
                    COALESCE(meta_ad_account_id, '') AS meta_ad_account_id,
                    campaign_external_id, campaign_name, campaign_objective,
                    optimization_goal, result_type
                FROM meta_ads_campaign_performance
                WHERE import_id=CAST(:import_id AS UUID)
                ORDER BY COALESCE(meta_ad_account_id, ''), COALESCE(campaign_external_id, campaign_name), source_row_number
            """), {"import_id": import_id}).mappings().all()
            stored = conn.execute(text("""
                SELECT * FROM meta_ads_campaign_objective_mappings
                WHERE client_id=CAST(:client_id AS UUID)
                  AND (campaign_external_id IS NOT NULL OR meta_ads_report_period_id=CAST(:period_id AS UUID))
            """), {"client_id": client_id, "period_id": period_id}).mappings().all()
            adsets = conn.execute(text("""
                SELECT DISTINCT COALESCE(meta_ad_account_id, '') AS meta_ad_account_id,
                    campaign_external_id, campaign_name, adset_external_id, adset_name
                FROM meta_ads_adset_performance
                WHERE import_id=CAST(:import_id AS UUID)
                ORDER BY campaign_name, adset_name
            """), {"import_id": import_id}).mappings().all()
        by_external = {(row["meta_ad_account_id"], row["campaign_external_id"]): dict(row) for row in stored if row["campaign_external_id"]}
        by_period = {row["campaign_key"]: dict(row) for row in stored if not row["campaign_external_id"]}
        result = []
        for row in rows:
            account_id = row["meta_ad_account_id"] or ""
            external_id = row["campaign_external_id"]
            campaign_key = external_id or f"csv:{str(row['campaign_name']).casefold()}"
            mapping = by_external.get((account_id, external_id)) if external_id else by_period.get(campaign_key)
            optimization_goals = list((mapping or {}).get("optimization_goals") or ([row["optimization_goal"]] if row["optimization_goal"] else []))
            result_types = list((mapping or {}).get("result_types") or ([row["result_type"]] if row["result_type"] else []))
            suggestion = suggest_meta_objective(row["campaign_objective"], optimization_goals, result_types)
            campaign_adsets = [
                {"id": item["adset_external_id"] or item["adset_name"], "external_id": item["adset_external_id"], "name": item["adset_name"]}
                for item in adsets
                if (external_id and item["campaign_external_id"] == external_id)
                or (not external_id and item["campaign_name"] == row["campaign_name"])
            ]
            result.append({
                "campaign_key": campaign_key,
                "meta_ad_account_id": account_id,
                "campaign_external_id": external_id,
                "campaign_name": row["campaign_name"],
                "detected_objective": row["campaign_objective"],
                "optimization_goals": optimization_goals,
                "result_types": result_types,
                "suggested_objective": (mapping or {}).get("suggested_objective") or suggestion["objective"],
                "suggestion_confidence": (mapping or {}).get("suggestion_confidence") or suggestion["confidence"],
                "reporting_objective": (mapping or {}).get("reporting_objective"),
                "is_confirmed": bool((mapping or {}).get("is_confirmed")),
                "is_included": (mapping or {}).get("is_included", True),
                "adsets": campaign_adsets,
            })
        return {"campaigns": result, "unconfirmed_count": sum(not row["is_confirmed"] for row in result)}

    def save_campaign_mappings(self, client_id: str, period_id: str, payload: dict) -> dict:
        UUID(client_id); UUID(period_id)
        campaigns = payload.get("campaigns")
        if not isinstance(campaigns, list) or not campaigns:
            raise ValueError("Select at least one Campaign mapping.")
        allowed_objectives = {item["key"] for item in OBJECTIVE_CATALOG["meta"]["objectives"]}
        with self.engine.begin() as conn:
            for item in campaigns:
                reporting_objective = str(item.get("reporting_objective") or "").lower()
                if reporting_objective not in allowed_objectives:
                    raise ValueError("Every Campaign must have a supported reporting objective.")
                external_id = str(item.get("campaign_external_id") or "").strip() or None
                account_id = str(item.get("meta_ad_account_id") or "").strip()
                campaign_name = str(item.get("campaign_name") or "Unnamed campaign").strip()
                campaign_key = str(item.get("campaign_key") or external_id or f"csv:{campaign_name.casefold()}")
                params = {
                    "client_id": client_id, "period_id": period_id, "account_id": account_id,
                    "external_id": external_id, "campaign_key": campaign_key, "campaign_name": campaign_name,
                    "detected": item.get("detected_objective"),
                    "optimization": _json(item.get("optimization_goals") or []),
                    "result_types": _json(item.get("result_types") or []),
                    "suggested": item.get("suggested_objective") or reporting_objective,
                    "confidence": item.get("suggestion_confidence") or "manual",
                    "reporting": reporting_objective, "included": bool(item.get("is_included", True)),
                }
                if external_id:
                    conn.execute(text("""
                        INSERT INTO meta_ads_campaign_objective_mappings (
                            client_id, meta_ad_account_id, campaign_external_id, campaign_key, campaign_name,
                            detected_objective, optimization_goals, result_types, suggested_objective,
                            suggestion_confidence, reporting_objective, is_confirmed, is_included
                        ) VALUES (
                            CAST(:client_id AS UUID), :account_id, :external_id, :campaign_key, :campaign_name,
                            :detected, CAST(:optimization AS JSONB), CAST(:result_types AS JSONB), :suggested,
                            :confidence, :reporting, TRUE, :included
                        ) ON CONFLICT (client_id, meta_ad_account_id, campaign_external_id)
                        WHERE campaign_external_id IS NOT NULL DO UPDATE SET
                            campaign_name=EXCLUDED.campaign_name, reporting_objective=EXCLUDED.reporting_objective,
                            is_confirmed=TRUE, is_included=EXCLUDED.is_included, updated_at=now()
                    """), params)
                else:
                    conn.execute(text("""
                        INSERT INTO meta_ads_campaign_objective_mappings (
                            client_id, meta_ads_report_period_id, meta_ad_account_id, campaign_key, campaign_name,
                            detected_objective, optimization_goals, result_types, suggested_objective,
                            suggestion_confidence, reporting_objective, is_confirmed, is_included
                        ) VALUES (
                            CAST(:client_id AS UUID), CAST(:period_id AS UUID), :account_id, :campaign_key, :campaign_name,
                            :detected, CAST(:optimization AS JSONB), CAST(:result_types AS JSONB), :suggested,
                            :confidence, :reporting, TRUE, :included
                        ) ON CONFLICT (meta_ads_report_period_id, campaign_key)
                        WHERE campaign_external_id IS NULL DO UPDATE SET
                            campaign_name=EXCLUDED.campaign_name, reporting_objective=EXCLUDED.reporting_objective,
                            is_confirmed=TRUE, is_included=EXCLUDED.is_included, updated_at=now()
                    """), params)
            conn.execute(text("""
                UPDATE meta_ads_report_periods
                SET configuration = COALESCE(configuration, '{}'::jsonb)
                    || jsonb_build_object('objective_model', 'canonical'),
                    updated_at=now()
                WHERE id=CAST(:period_id AS UUID) AND client_id=CAST(:client_id AS UUID)
            """), {"period_id": period_id, "client_id": client_id})
        return self.campaign_mappings(client_id, period_id)

    def analysis(self, client_id: str, period_id: str, dimension: str, filters: dict | None = None) -> dict:
        UUID(client_id); UUID(period_id)
        dimension = str(dimension or "").lower()
        if dimension not in {"creative", "adset"}:
            raise ValueError("Analysis dimension must be creative or adset.")
        filters = filters or {}
        platform_scope = str(filters.get("platform_scope") or "meta").lower()
        if platform_scope not in {"meta", "instagram", "facebook"}:
            raise ValueError("Meta platform scope must be All Meta, Instagram, or Facebook.")
        requested_objective = str(filters.get("objective") or "").lower()
        campaign_filter = {str(item) for item in (filters.get("campaign_ids") or []) if str(item)}
        adset_filter = {str(item) for item in (filters.get("adset_ids") or []) if str(item)}

        mappings_payload = self.campaign_mappings(client_id, period_id)
        confirmed = [row for row in mappings_payload["campaigns"] if row["is_confirmed"] and row["is_included"]]
        objectives = []
        for row in confirmed:
            if row["reporting_objective"] not in objectives:
                objectives.append(row["reporting_objective"])
        objective_key = requested_objective if requested_objective in objectives else (objectives[0] if objectives else requested_objective)
        if objective_key:
            objective_definition("meta", objective_key)

        with self.engine.connect() as conn:
            active_rows = conn.execute(text("""
                SELECT active.platform, active.import_id, i.source, i.schema_version, i.imported_at, i.sync_completed_at,
                    i.date_preset, i.data_start, i.data_end
                FROM meta_ads_active_snapshots active
                JOIN meta_ads_imports i ON i.id=active.import_id
                WHERE active.meta_ads_report_period_id=CAST(:period_id AS UUID)
                  AND i.client_id=CAST(:client_id AS UUID) AND i.status='success'
            """), {"client_id": client_id, "period_id": period_id}).mappings().all()
            active = {row["platform"]: dict(row) for row in active_rows}
            if platform_scope == "meta":
                active_ids = {str(row["import_id"]) for row in active.values()}
                if len(active_ids) > 1 or not {"instagram", "facebook"}.issubset(active):
                    return {
                        "dimension": dimension, "platform_scope": platform_scope,
                        "objective": objective_key or None, "objectives": objectives,
                        "data_status": "source_mismatch", "rows": [], "summary": {},
                        "display_metrics": [], "available_filters": {"campaigns": confirmed, "adsets": []},
                        "unconfirmed_count": mappings_payload["unconfirmed_count"],
                        "warnings": ["All Meta requires Instagram and Facebook from the same active snapshot. Align their data source or select one platform."],
                    }
                snapshot = next(iter(active.values()), None)
            else:
                snapshot = active.get(platform_scope)
            if not snapshot:
                return {
                    "dimension": dimension, "platform_scope": platform_scope,
                    "objective": objective_key or None, "objectives": objectives,
                    "data_status": "missing_data", "rows": [], "summary": {},
                    "display_metrics": [], "available_filters": {"campaigns": confirmed, "adsets": []},
                    "unconfirmed_count": mappings_payload["unconfirmed_count"], "warnings": [],
                }
            import_id = snapshot["import_id"]
            columns = """
                id AS row_id, meta_ad_account_id, campaign_external_id, campaign_name,
                adset_external_id, adset_name, ad_external_id, ad_name,
                source_row_key, source_row_number, reach, impressions, post_engagements,
                interactions, post_shares, post_saves, post_reactions, post_comments,
                link_clicks, destination_clicks, frequency, spend, video_views, thruplay,
                leads, profile_visits, page_likes, result_value, result_type
            """
            if platform_scope == "meta":
                table = "meta_ads_ad_performance" if dimension == "creative" else "meta_ads_adset_performance"
                raw_columns = columns if dimension == "creative" else columns.replace(
                    "adset_external_id, adset_name, ad_external_id, ad_name,",
                    "adset_external_id, adset_name, NULL::TEXT AS ad_external_id, NULL::TEXT AS ad_name,",
                )
                raw_rows = conn.execute(text(f"SELECT {raw_columns} FROM {table} WHERE import_id=CAST(:import_id AS UUID) ORDER BY source_row_number"), {"import_id": import_id}).mappings().all()
                raw_rows = self._apply_data_overrides(
                    conn, import_id, "ad" if dimension == "creative" else "adset", raw_rows,
                )
                summary_table = "meta_ads_adset_performance" if adset_filter else "meta_ads_campaign_performance"
                entity_columns = (
                    "id AS row_id, meta_ad_account_id, campaign_external_id, campaign_name, "
                    + ("adset_external_id, adset_name, " if adset_filter else "NULL::TEXT AS adset_external_id, NULL::TEXT AS adset_name, ")
                    + "NULL::TEXT AS ad_external_id, NULL::TEXT AS ad_name, source_row_key, source_row_number, "
                    + "reach, impressions, post_engagements, interactions, post_shares, post_saves, post_reactions, post_comments, "
                    + "link_clicks, destination_clicks, frequency, spend, video_views, thruplay, leads, profile_visits, page_likes, result_value, result_type"
                )
                summary_rows = conn.execute(text(f"SELECT {entity_columns} FROM {summary_table} WHERE import_id=CAST(:import_id AS UUID) ORDER BY source_row_number"), {"import_id": import_id}).mappings().all()
                summary_rows = self._apply_data_overrides(
                    conn, import_id, "adset" if adset_filter else "campaign", summary_rows,
                )
            else:
                raw_rows = conn.execute(text(f"""
                    SELECT {columns}, placement, device_platform
                    FROM meta_ads_placement_breakdown
                    WHERE import_id=CAST(:import_id AS UUID)
                      AND LOWER(COALESCE(publisher_platform, ''))=:platform
                    ORDER BY source_row_number
                """), {"import_id": import_id, "platform": platform_scope}).mappings().all()
                raw_rows = self._apply_data_overrides(conn, import_id, "placement", raw_rows)
                summary_rows = raw_rows
            creative_rows = conn.execute(text("""
                SELECT ad_external_id, MAX(thumbnail_url) AS thumbnail_url, MAX(image_url) AS image_url,
                    MAX(preview_url) AS preview_url, MAX(permalink_url) AS permalink_url
                FROM meta_ads_creatives WHERE import_id=CAST(:import_id AS UUID)
                GROUP BY ad_external_id
            """), {"import_id": import_id}).mappings().all()
            ads_count_rows = conn.execute(text("""
                SELECT COALESCE(adset_external_id, adset_name) AS adset_key,
                    COUNT(DISTINCT COALESCE(ad_external_id, ad_name)) AS ads_count
                FROM meta_ads_ad_performance
                WHERE import_id=CAST(:import_id AS UUID)
                GROUP BY COALESCE(adset_external_id, adset_name)
            """), {"import_id": import_id}).mappings().all()

        mapping_external = {
            (row["meta_ad_account_id"] or "", str(row["campaign_external_id"])): row
            for row in confirmed if row["campaign_external_id"]
        }
        mapping_names = {row["campaign_name"]: row for row in confirmed if not row["campaign_external_id"]}
        creative_assets = {str(row["ad_external_id"]): dict(row) for row in creative_rows if row["ad_external_id"]}
        ads_counts = {str(row["adset_key"]): int(row["ads_count"]) for row in ads_count_rows if row["adset_key"]}
        deduped = {}
        for source in raw_rows:
            source = dict(source)
            if platform_scope == "meta":
                entity = source.get("ad_external_id") if dimension == "creative" else source.get("adset_external_id")
                fallback = source.get("ad_name") if dimension == "creative" else source.get("adset_name")
                key = (source.get("meta_ad_account_id") or "", entity or fallback or source.get("source_row_key"))
            else:
                entity = source.get("ad_external_id") or source.get("ad_name") or source.get("source_row_key")
                key = (source.get("meta_ad_account_id") or "", entity, source.get("placement"), source.get("device_platform"))
            deduped[key] = source

        additive = (
            "reach", "impressions", "post_engagements", "interactions", "post_shares",
            "post_saves", "post_reactions", "post_comments", "link_clicks",
            "destination_clicks", "spend", "video_views", "thruplay", "leads",
            "profile_visits", "page_likes", "result_value",
        )
        grouped = {}
        filter_campaigns = []
        filter_adsets = {}
        for source in deduped.values():
            mapping = None
            if source.get("campaign_external_id"):
                mapping = mapping_external.get((source.get("meta_ad_account_id") or "", str(source["campaign_external_id"])))
            if mapping is None:
                mapping = mapping_names.get(source.get("campaign_name"))
            if not mapping or mapping.get("reporting_objective") != objective_key:
                continue
            campaign_id = str(source.get("campaign_external_id") or mapping["campaign_key"])
            adset_id = str(source.get("adset_external_id") or source.get("adset_name") or "")
            if not any(item["id"] == campaign_id for item in filter_campaigns):
                filter_campaigns.append({"id": campaign_id, "name": source.get("campaign_name") or mapping["campaign_name"]})
            if adset_id:
                filter_adsets[adset_id] = {"id": adset_id, "name": source.get("adset_name") or adset_id, "campaign_id": campaign_id}
            if campaign_filter and campaign_id not in campaign_filter:
                continue
            if adset_filter and adset_id not in adset_filter:
                continue
            entity_id = str((source.get("ad_external_id") or source.get("ad_name")) if dimension == "creative" else adset_id)
            if not entity_id:
                continue
            target = grouped.setdefault(entity_id, {
                "id": entity_id,
                "name": (source.get("ad_name") or "Unnamed ad") if dimension == "creative" else (source.get("adset_name") or "Unnamed ad set"),
                "campaign_id": campaign_id,
                "campaign_name": source.get("campaign_name") or mapping["campaign_name"],
                "adset_id": adset_id,
                "adset_name": source.get("adset_name"),
                "metrics": {field: None for field in additive},
            })
            for field in additive:
                value = source.get(field)
                if value is not None:
                    target["metrics"][field] = (target["metrics"][field] or 0.0) + float(value)
            if dimension == "creative":
                target.update(creative_assets.get(str(source.get("ad_external_id"))) or {})

        result_field = result_metric_for_objective(objective_key)
        rows = []
        for target in grouped.values():
            metrics = target["metrics"]
            if result_field == "video_views":
                result = metrics.get("thruplay") or metrics.get("video_views")
            else:
                result = metrics.get(result_field)
            metrics["result"] = result
            impressions = metrics.get("impressions")
            reach = metrics.get("reach")
            clicks = metrics.get("link_clicks")
            spend = metrics.get("spend")
            engagements = metrics.get("post_engagements")
            metrics.update({
                "clicks": clicks,
                "frequency": impressions / reach if impressions is not None and reach else None,
                "ctr": clicks / impressions * 100 if clicks is not None and impressions else None,
                "engagement_rate": engagements / impressions * 100 if engagements is not None and impressions else None,
                "result_rate": result / impressions * 100 if result is not None and impressions else None,
                "cost_per_result": spend / result if spend is not None and result else None,
                "cpm": spend / impressions * 1000 if spend is not None and impressions else None,
                "cpc": spend / clicks if spend is not None and clicks else None,
            })
            if dimension == "adset":
                target["ads_count"] = ads_counts.get(target["id"], 0)
            rows.append(target)
        rows.sort(key=lambda row: (row["metrics"].get("result") is not None, row["metrics"].get("result") or 0), reverse=True)

        configuration_rows = self.metric_configurations(client_id)["configurations"]
        selected_config = next((row for row in configuration_rows if row["scope"] == "meta" and row["objective"] == objective_key), None)
        display_keys = list(selected_config["metric_keys"]) if selected_config else []
        display_metrics = [{"key": key, **METRICS[key]} for key in display_keys]
        authoritative = {}
        for source in summary_rows:
            source = dict(source)
            mapping = mapping_external.get((source.get("meta_ad_account_id") or "", str(source.get("campaign_external_id")))) if source.get("campaign_external_id") else mapping_names.get(source.get("campaign_name"))
            if not mapping or mapping.get("reporting_objective") != objective_key:
                continue
            campaign_id = str(source.get("campaign_external_id") or mapping["campaign_key"])
            adset_id = str(source.get("adset_external_id") or source.get("adset_name") or "")
            if campaign_filter and campaign_id not in campaign_filter:
                continue
            if adset_filter and adset_id not in adset_filter:
                continue
            entity_key = adset_id if adset_filter else campaign_id
            authoritative[entity_key] = source
        summary_metrics = {field: None for field in additive}
        for source in authoritative.values():
            for field in additive:
                if source.get(field) is not None:
                    summary_metrics[field] = (summary_metrics[field] or 0.0) + float(source[field])
        summary_result = summary_metrics.get("thruplay") or summary_metrics.get("video_views") if result_field == "video_views" else summary_metrics.get(result_field)
        summary_metrics["result"] = summary_result
        summary = {key: summary_metrics.get(key) for key in display_keys}
        total_impressions = summary_metrics.get("impressions")
        total_reach = summary_metrics.get("reach")
        total_clicks = summary_metrics.get("link_clicks")
        total_spend = summary_metrics.get("spend")
        total_result = summary_result
        total_engagements = summary_metrics.get("post_engagements")
        summary.update({
            "frequency": total_impressions / total_reach if total_impressions is not None and total_reach else None,
            "ctr": total_clicks / total_impressions * 100 if total_clicks is not None and total_impressions else None,
            "engagement_rate": total_engagements / total_impressions * 100 if total_engagements is not None and total_impressions else None,
            "result_rate": total_result / total_impressions * 100 if total_result is not None and total_impressions else None,
            "cost_per_result": total_spend / total_result if total_spend is not None and total_result else None,
            "cpm": total_spend / total_impressions * 1000 if total_spend is not None and total_impressions else None,
            "cpc": total_spend / total_clicks if total_spend is not None and total_clicks else None,
        })
        warnings = []
        if platform_scope != "meta":
            warnings.append("Platform-scoped reach can overlap across placements; use All Meta for authoritative Campaign and Ad Set totals.")
        return {
            "dimension": dimension, "platform_scope": platform_scope,
            "objective": objective_key or None, "objectives": objectives,
            "data_status": "ready" if objective_key else "needs_mapping",
            "rows": rows, "summary": summary, "display_metrics": display_metrics,
            "available_filters": {"campaigns": filter_campaigns, "adsets": list(filter_adsets.values())},
            "unconfirmed_count": mappings_payload["unconfirmed_count"],
            "source": {"import_id": import_id, "type": snapshot["source"], "updated_at": snapshot["sync_completed_at"] or snapshot["imported_at"],
                "date_preset": snapshot.get("date_preset"), "data_start": snapshot.get("data_start"), "data_end": snapshot.get("data_end")},
            "warnings": warnings,
        }

    def select_source(self, client_id: str, period_id: str, platform: str, import_id: str) -> dict:
        platform = str(platform).lower()
        if platform not in {"instagram", "facebook"}:
            raise ValueError("Only Instagram and Facebook sources can be selected.")
        with self.engine.begin() as conn:
            snapshot = conn.execute(text("SELECT id, platform_scope FROM meta_ads_imports WHERE id=CAST(:import_id AS UUID) AND client_id=CAST(:client_id AS UUID) AND meta_ads_report_period_id=CAST(:period_id AS UUID) AND status='success'"), {"import_id": import_id, "client_id": client_id, "period_id": period_id}).mappings().first()
            if not snapshot or platform not in (snapshot.get("platform_scope") or []):
                raise ValueError("Snapshot is not available for this platform.")
            self._activate_snapshot(conn, period_id, platform, import_id)
            return {"platform": platform, "import_id": import_id, "active": True}

    def creative_detail(self, client_id: str, period_id: str, creative_id: str, platform_scope: str = "meta") -> dict:
        UUID(client_id); UUID(period_id)
        platform_scope = str(platform_scope or "meta").lower()
        if platform_scope not in {"meta", "instagram", "facebook"}:
            raise ValueError("Unsupported Meta platform scope.")
        with self.engine.connect() as conn:
            active_rows = conn.execute(text("""
                SELECT active.platform, active.import_id
                FROM meta_ads_active_snapshots active
                JOIN meta_ads_imports i ON i.id=active.import_id
                WHERE active.meta_ads_report_period_id=CAST(:period_id AS UUID)
                  AND i.client_id=CAST(:client_id AS UUID) AND i.status='success'
            """), {"client_id": client_id, "period_id": period_id}).mappings().all()
            active = {row["platform"]: row["import_id"] for row in active_rows}
            if platform_scope == "meta":
                import_ids = {str(value) for value in active.values()}
                if len(import_ids) != 1 or not {"instagram", "facebook"}.issubset(active):
                    raise ValueError("All Meta requires Instagram and Facebook from the same active snapshot.")
                import_id = next(iter(active.values()))
            else:
                import_id = active.get(platform_scope)
            if not import_id:
                raise ValueError("No active data source is available for this platform.")
            params = {"import_id": import_id, "creative_id": creative_id, "platform": platform_scope}
            creative = conn.execute(text("""
                SELECT performance.ad_external_id, performance.ad_name, performance.campaign_name,
                    performance.adset_name, creative.thumbnail_url, creative.image_url,
                    creative.preview_url, creative.permalink_url, creative.creative_fetched_at
                FROM meta_ads_ad_performance performance
                LEFT JOIN meta_ads_creatives creative ON creative.import_id=performance.import_id
                    AND creative.ad_external_id=performance.ad_external_id
                WHERE performance.import_id=CAST(:import_id AS UUID)
                  AND COALESCE(performance.ad_external_id, performance.ad_name)=:creative_id
                ORDER BY performance.source_row_number LIMIT 1
            """), params).mappings().first()
            if not creative:
                raise ValueError("Creative was not found in the active snapshot.")
            platform_clause = "" if platform_scope == "meta" else "AND LOWER(COALESCE(publisher_platform, ''))=:platform"
            placements = conn.execute(text(f"""
                SELECT COALESCE(NULLIF(publisher_platform,''), 'Unknown') AS publisher_platform,
                    COALESCE(NULLIF(placement,''), 'Unknown') AS placement,
                    COALESCE(NULLIF(device_platform,''), 'Unknown') AS device,
                    impressions, reach, spend
                FROM meta_ads_placement_breakdown
                WHERE import_id=CAST(:import_id AS UUID)
                  AND COALESCE(ad_external_id, ad_name)=:creative_id {platform_clause}
                ORDER BY impressions DESC NULLS LAST LIMIT 50
            """), params).mappings().all()
            demographics = conn.execute(text("""
                SELECT COALESCE(NULLIF(age,''), 'Unknown') AS age,
                    COALESCE(NULLIF(gender,''), 'Unknown') AS gender,
                    impressions, reach
                FROM meta_ads_demographic_breakdown
                WHERE import_id=CAST(:import_id AS UUID)
                  AND COALESCE(ad_external_id, ad_name)=:creative_id
                ORDER BY impressions DESC NULLS LAST LIMIT 50
            """), params).mappings().all()
            regions = conn.execute(text("""
                SELECT COALESCE(NULLIF(region,''), 'Unknown') AS region, impressions, reach
                FROM meta_ads_region_breakdown
                WHERE import_id=CAST(:import_id AS UUID)
                  AND COALESCE(ad_external_id, ad_name)=:creative_id
                ORDER BY impressions DESC NULLS LAST LIMIT 50
            """), params).mappings().all()
        return {
            "creative": dict(creative),
            "placements": [dict(row) for row in placements],
            "demographics": [dict(row) for row in demographics],
            "regions": [dict(row) for row in regions],
            "caveat": "Demographic and region breakdowns are shared Meta exports and may not be platform-exclusive. Creative URLs can expire; sync again if a preview no longer loads.",
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
                        COALESCE((SELECT jsonb_agg(jsonb_build_object(
                            'id', account.ad_account_id, 'name', account.account_name,
                            'account_status', account.account_status, 'currency', account.currency,
                            'timezone_name', account.timezone_name, 'is_active', account.is_active
                        ) ORDER BY account.account_name) FROM client_meta_ad_accounts account
                        WHERE account.client_id=c.id), '[]'::jsonb) AS meta_ad_accounts,
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
                        i.source AS active_source,
                        i.imported_at,
                        i.sync_completed_at,
                        i.selected_ad_account_ids,
                        i.platform_scope,
                        i.date_preset,
                        i.data_start,
                        i.data_end,
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
                    LEFT JOIN LATERAL (
                        SELECT selected_import.*
                        FROM meta_ads_active_snapshots active
                        JOIN meta_ads_imports selected_import ON selected_import.id = active.import_id
                        WHERE active.meta_ads_report_period_id = p.id
                        ORDER BY active.selected_at DESC LIMIT 1
                    ) i ON TRUE
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
                stored_period_configuration = period.get("ads_configuration") or {}
                is_canonical = stored_period_configuration.get("objective_model") == "canonical"
                period_configuration = ads_period_configuration(
                    None if is_canonical else (stored_period_configuration or legacy_goal_configuration),
                    configuration["platforms"],
                )
                period["ads_configuration"] = stored_period_configuration if is_canonical else period_configuration
                period["objective_model"] = "canonical" if is_canonical else "legacy"
                period["objective_configs"] = stored_period_configuration.get("objective_configs", {}) if is_canonical else {}
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
                        i.imported_at,
                        i.source AS active_source,
                        i.selected_ad_account_ids,
                        i.platform_scope,
                        i.date_preset,
                        i.data_start,
                        i.data_end,
                        i.warnings AS sync_warnings,
                        i.sync_completed_at
                    FROM clients c
                    JOIN client_products cp
                      ON cp.client_id = c.id
                     AND cp.product = 'meta_ads'
                     AND cp.is_active
                    JOIN meta_ads_report_periods p
                      ON p.client_id = c.id
                     AND p.id = CAST(:period_id AS UUID)
                    LEFT JOIN meta_ads_active_snapshots active
                      ON active.meta_ads_report_period_id = p.id
                     AND active.platform = :platform
                    LEFT JOIN meta_ads_imports i ON i.id = active.import_id
                    WHERE c.id = CAST(:client_id AS UUID)
                      AND c.is_active
                    """
                ),
                {"client_id": client_id, "period_id": period_id, "platform": platform},
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

            stored_period_configuration = context.get("period_configuration") or {}
            if stored_period_configuration.get("objective_model") == "canonical":
                mappings = self.campaign_mappings(client_id, period_id)
                confirmed_objectives = {
                    row["reporting_objective"]
                    for row in mappings["campaigns"]
                    if row["is_confirmed"] and row["is_included"] and row.get("reporting_objective")
                }
                objective_configs = (
                    (stored_period_configuration.get("objective_configs") or {}).get("meta") or {}
                )
                goal_configs = [
                    {
                        "key": goal["key"],
                        "target_monthly": (objective_configs.get(goal["key"]) or {}).get("target_monthly"),
                        "budget_monthly": (objective_configs.get(goal["key"]) or {}).get("budget_monthly"),
                        "target_cost_per_result": (objective_configs.get(goal["key"]) or {}).get("target_cost_per_result"),
                    }
                    for goal in ADS_GOAL_DEFINITIONS[platform]
                    if goal["key"] in confirmed_objectives
                ]
            else:
                goal_configs = period_configuration["goals"].get(platform, [])

            definition = next(
                item
                for item in ads_platform_catalog(configuration, period_configuration)
                if item["key"] == platform
            )
            definition = {**definition, "active_goals": goal_configs}
            response = {
                "platform": definition,
                "period": {
                    key: context.get(key)
                    for key in (
                        "period_id",
                        "period_label",
                        "period_start",
                        "period_end",
                        "import_id",
                        "import_status",
                        "imported_at",
                        "sync_completed_at",
                        "active_source",
                        "selected_ad_account_ids",
                        "platform_scope",
                        "date_preset",
                        "data_start",
                        "data_end",
                        "sync_warnings",
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

            def effective_placement(field: str, alias: str = "performance") -> str:
                return (
                    f"COALESCE(NULLIF({alias}_overrides.data->>'{field}', '')::numeric, "
                    f"{alias}.{field})"
                )

            def placement_override_join(alias: str = "performance") -> str:
                return f"""
                    LEFT JOIN LATERAL (
                        SELECT jsonb_object_agg(editor.field_key, editor.override_value) AS data
                        FROM meta_ads_data_overrides editor
                        WHERE editor.import_id={alias}.import_id
                          AND editor.entity_type='placement'
                          AND editor.entity_row_id={alias}.id
                          AND editor.is_active
                    ) {alias}_overrides ON TRUE
                """

            for goal_config in goal_configs:
                goal_key = goal_config["key"]
                result_types = list(META_GOAL_RESULT_TYPES.get(goal_key, ()))
                goal_definition = next(
                    item for item in (*ADS_GOAL_DEFINITIONS[platform], *LEGACY_ADS_GOAL_DEFINITIONS.get(platform, ()))
                    if item["key"] == goal_key
                )
                primary_metric = (
                    "post_engagements" if goal_key == "engagement" else "result_value"
                )
                totals = conn.execute(
                    text(
                        f"""
                        SELECT
                            COALESCE(SUM({effective_placement(primary_metric)}), 0) AS result_value,
                            COALESCE(SUM({effective_placement('spend')}), 0) AS spend,
                            COALESCE(SUM({effective_placement('impressions')}), 0) AS impressions,
                            COALESCE(SUM({effective_placement('reach')}), 0) AS reach,
                            COALESCE(SUM({effective_placement('post_engagements')}), 0) AS engagements,
                            COALESCE(SUM({effective_placement('link_clicks')}), 0) AS link_clicks,
                            COALESCE(SUM(performance.instagram_follows), 0) AS follows,
                            COALESCE(SUM(performance.page_engagements), 0) AS page_engagements
                        FROM meta_ads_placement_breakdown performance
                        {placement_override_join()}
                        WHERE performance.import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(performance.publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(performance.result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
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
                        JOIN meta_ads_report_periods p ON p.id = r.meta_ads_report_period_id
                        JOIN meta_ads_active_snapshots active
                          ON active.meta_ads_report_period_id = p.id
                         AND active.platform = :platform
                         AND active.import_id = r.import_id
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
                            COALESCE(NULLIF(performance.ad_name, ''), 'Unnamed ad') AS label,
                            MAX(creative.thumbnail_url) AS thumbnail_url,
                            MAX(creative.image_url) AS image_url,
                            MAX(creative.preview_url) AS preview_url,
                            MAX(creative.permalink_url) AS permalink_url,
                            COALESCE(SUM({effective_placement(primary_metric)}), 0) AS result_value,
                            COALESCE(SUM({effective_placement('reach')}), 0) AS reach,
                            COALESCE(SUM({effective_placement('impressions')}), 0) AS impressions,
                            COALESCE(SUM({effective_placement('post_engagements')}), 0) AS engagements,
                            COALESCE(SUM({effective_placement('link_clicks')}), 0) AS link_clicks,
                            COALESCE(SUM({effective_placement('spend')}), 0) AS spend
                        FROM meta_ads_placement_breakdown performance
                        {placement_override_join()}
                        LEFT JOIN meta_ads_creatives creative
                          ON creative.import_id = performance.import_id
                         AND creative.ad_external_id = performance.ad_external_id
                        WHERE performance.import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(performance.publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(performance.result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        GROUP BY COALESCE(NULLIF(performance.ad_name, ''), 'Unnamed ad')
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
                            COALESCE(NULLIF(performance.placement, ''), 'Unknown placement') AS label,
                            COALESCE(SUM({effective_placement(primary_metric)}), 0) AS result_value,
                            COALESCE(SUM({effective_placement('impressions')}), 0) AS impressions,
                            COALESCE(SUM({effective_placement('spend')}), 0) AS spend
                        FROM meta_ads_placement_breakdown performance
                        {placement_override_join()}
                        WHERE performance.import_id = CAST(:import_id AS UUID)
                          AND LOWER(COALESCE(performance.publisher_platform, '')) = :platform
                          AND LOWER(COALESCE(performance.result_type, '')) = ANY(CAST(:result_types AS TEXT[]))
                        GROUP BY COALESCE(NULLIF(performance.placement, ''), 'Unknown placement')
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
                        NULL::UUID AS import_id,
                        NULL::TEXT AS import_status
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
            stored_period_configuration = context.get("period_configuration") or {}
            if stored_period_configuration.get("objective_model") == "canonical":
                objective_configs = stored_period_configuration.get("objective_configs") or {}
                meta_configs = objective_configs.get("meta") or {}
                mappings = self.campaign_mappings(client_id, period_id)
                objective_keys = []
                for mapping in mappings["campaigns"]:
                    if mapping["is_confirmed"] and mapping["is_included"] and mapping["reporting_objective"] not in objective_keys:
                        objective_keys.append(mapping["reporting_objective"])
                rows = []
                for objective_key in objective_keys:
                    analysis = self.analysis(client_id, period_id, "adset", {"platform_scope": "meta", "objective": objective_key})
                    config = meta_configs.get(objective_key) or {}
                    target = config.get("target_monthly")
                    budget = config.get("budget_monthly")
                    actual = analysis.get("summary", {}).get("result")
                    if actual is None:
                        primary = result_metric_for_objective(objective_key)
                        actual = analysis.get("summary", {}).get(primary)
                    spend = analysis.get("summary", {}).get("spend")
                    rows.append({
                        "platform": "meta", "platform_label": "All Meta", "goal_key": objective_key,
                        "goal_label": objective_definition("meta", objective_key)["label"],
                        "target_monthly": target, "target_total": target,
                        "budget_monthly": budget, "budget_total": budget,
                        "actual_monthly": actual, "actual_total": actual,
                        "spend_monthly": spend, "spend_total": spend,
                        "achievement_monthly": actual / float(target) * 100 if actual is not None and target else None,
                        "achievement_total": actual / float(target) * 100 if actual is not None and target else None,
                        "budget_use_monthly": spend / float(budget) * 100 if spend is not None and budget else None,
                        "budget_use_total": spend / float(budget) * 100 if spend is not None and budget else None,
                        "status": analysis.get("data_status", "missing_data"),
                    })
                return {"period_id": period_id, "period_label": context["period_label"], "rows": rows, "objective_model": "canonical", "unconfirmed_count": mappings["unconfirmed_count"]}
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
            active_imports = {
                row["platform"]: dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT active.platform, i.id AS import_id, i.status AS import_status
                        FROM meta_ads_active_snapshots active
                        JOIN meta_ads_imports i ON i.id=active.import_id
                        WHERE active.meta_ads_report_period_id=CAST(:period_id AS UUID)
                        """
                    ), {"period_id": period_id},
                ).mappings()
            }
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
                active_import = active_imports.get(platform, {})
                for goal_config in period_configuration["goals"].get(platform, []):
                    goal_key = goal_config["key"]
                    goal_definition = next(
                        item for item in (*ADS_GOAL_DEFINITIONS[platform], *LEGACY_ADS_GOAL_DEFINITIONS.get(platform, ()))
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
                        and active_import.get("import_id")
                        and active_import.get("import_status") == "success"
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
                                "import_id": active_import["import_id"],
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
                                JOIN meta_ads_report_periods p ON p.id = r.meta_ads_report_period_id
                                JOIN meta_ads_active_snapshots active
                                  ON active.meta_ads_report_period_id=p.id
                                 AND active.platform=:platform
                                 AND active.import_id=r.import_id
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
            if (payload or {}).get("objective_model") == "canonical" or "objective_configs" in (payload or {}):
                raw_configs = (payload or {}).get("objective_configs") or {}
                normalized_meta = {}
                for objective_key, raw in (raw_configs.get("meta") or {}).items():
                    objective_definition("meta", objective_key)
                    values = {}
                    for field in ("target_monthly", "budget_monthly", "target_cost_per_result"):
                        value = raw.get(field)
                        if value in (None, ""):
                            values[field] = None
                        else:
                            number = float(value)
                            if number < 0:
                                raise ValueError(f"{field} cannot be negative.")
                            values[field] = number
                    adset_targets = raw.get("adset_targets") or []
                    if not isinstance(adset_targets, list):
                        raise ValueError("adset_targets must be a list.")
                    values["adset_targets"] = adset_targets
                    normalized_meta[objective_key] = values
                period_configuration = {
                    "version": 2,
                    "objective_model": "canonical",
                    "objective_configs": {"meta": normalized_meta},
                }
            else:
                period_configuration = ads_period_configuration(payload or {}, product_configuration["platforms"])
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
                "goals": period_configuration.get("goals", {}),
                "objective_configs": period_configuration.get("objective_configs", {}),
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
