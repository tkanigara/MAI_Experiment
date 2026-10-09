BEGIN;

ALTER TABLE meta_ads_imports
    ADD COLUMN IF NOT EXISTS date_preset TEXT,
    ADD COLUMN IF NOT EXISTS data_start DATE,
    ADD COLUMN IF NOT EXISTS data_end DATE;

UPDATE meta_ads_imports i
SET data_start = COALESCE(i.data_start, p.period_start),
    data_end = COALESCE(i.data_end, p.period_end),
    date_preset = COALESCE(i.date_preset, CASE WHEN i.source='csv' THEN 'csv_export' ELSE 'legacy_period' END)
FROM meta_ads_report_periods p
WHERE p.id=i.meta_ads_report_period_id
  AND (i.data_start IS NULL OR i.data_end IS NULL OR i.date_preset IS NULL);

ALTER TABLE meta_ads_imports
    ADD CONSTRAINT chk_meta_ads_import_data_range
    CHECK (data_start IS NULL OR data_end IS NULL OR data_end >= data_start);

CREATE INDEX IF NOT EXISTS idx_meta_ads_import_range
    ON meta_ads_imports (meta_ads_report_period_id, data_start, data_end);

COMMIT;
