from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import text

try:
    from dashboard.db import create_db_engine
    from dashboard.services.ads_workspace import (
        ads_platform_catalog,
        ads_product_configuration,
    )
except ModuleNotFoundError:
    from db import create_db_engine
    from services.ads_workspace import ads_platform_catalog, ads_product_configuration


TABLES = {
    "campaign": "meta_ads_campaign_performance",
    "adset": "meta_ads_adset_performance",
    "ad": "meta_ads_ad_performance",
    "placement": "meta_ads_placement_breakdown",
    "demographic": "meta_ads_demographic_breakdown",
    "region": "meta_ads_region_breakdown",
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
            configuration = ads_product_configuration(
                client.get("ads_configuration") or None
            )
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
                periods.append(period)
            return {
                "client": client,
                "platforms": ads_platform_catalog(configuration["platforms"]),
                "periods": periods,
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
