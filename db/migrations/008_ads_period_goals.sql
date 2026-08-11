BEGIN;

ALTER TABLE meta_ads_report_periods
    ADD COLUMN IF NOT EXISTS configuration JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
