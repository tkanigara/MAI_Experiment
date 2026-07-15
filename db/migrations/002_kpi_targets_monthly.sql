BEGIN;

ALTER TABLE kpi_targets
    ADD COLUMN IF NOT EXISTS period_month INTEGER;

UPDATE kpi_targets
SET period_month = COALESCE(
    (
        SELECT EXTRACT(MONTH FROM rp.period_start)::INTEGER
        FROM kpi_results kr
        JOIN report_periods rp ON rp.id = kr.report_period_id
        WHERE kr.kpi_target_id = kpi_targets.id
        ORDER BY rp.period_start DESC
        LIMIT 1
    ),
    1
)
WHERE period_month IS NULL;

ALTER TABLE kpi_targets
    ALTER COLUMN period_month SET NOT NULL;

ALTER TABLE kpi_targets
    DROP CONSTRAINT IF EXISTS kpi_targets_client_id_platform_metric_name_period_year_key;

ALTER TABLE kpi_targets
    DROP CONSTRAINT IF EXISTS kpi_targets_client_id_platform_metric_name_period_year_period_month_key;

ALTER TABLE kpi_targets
    ADD CONSTRAINT kpi_targets_client_id_platform_metric_name_period_year_period_month_key
    UNIQUE (client_id, platform, metric_name, period_year, period_month);

ALTER TABLE kpi_targets
    DROP CONSTRAINT IF EXISTS kpi_targets_period_month_check;

ALTER TABLE kpi_targets
    ADD CONSTRAINT kpi_targets_period_month_check
    CHECK (period_month BETWEEN 1 AND 12);

DROP INDEX IF EXISTS idx_kpi_targets_lookup;

CREATE INDEX idx_kpi_targets_lookup
    ON kpi_targets (client_id, platform, period_year, period_month, metric_name);

COMMIT;
