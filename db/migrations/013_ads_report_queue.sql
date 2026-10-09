BEGIN;

ALTER TABLE report_generation_jobs
    ADD COLUMN IF NOT EXISTS report_type TEXT;

UPDATE report_generation_jobs
SET report_type = CASE
    WHEN COALESCE(result_metadata ->> 'report_type', '')
         IN ('ads', 'meta_ads', 'paid_ads')
    THEN 'meta_ads'
    ELSE 'social_media'
END
WHERE report_type IS NULL;

ALTER TABLE report_generation_jobs
    ALTER COLUMN report_type SET DEFAULT 'social_media',
    ALTER COLUMN report_type SET NOT NULL;

ALTER TABLE report_generation_jobs
    DROP CONSTRAINT IF EXISTS report_generation_jobs_report_period_id_fkey;

ALTER TABLE report_generation_jobs
    DROP CONSTRAINT IF EXISTS report_generation_jobs_report_type_check;

ALTER TABLE report_generation_jobs
    ADD CONSTRAINT report_generation_jobs_report_type_check
    CHECK (report_type IN ('social_media', 'meta_ads'));

DROP INDEX IF EXISTS uq_report_generation_jobs_active_period;
CREATE UNIQUE INDEX uq_report_generation_jobs_active_period
    ON report_generation_jobs (client_id, report_type, report_period_id)
    WHERE status IN ('queued', 'running', 'retrying', 'cancel_requested');

DROP INDEX IF EXISTS idx_report_generation_jobs_period_history;
CREATE INDEX idx_report_generation_jobs_period_history
    ON report_generation_jobs (
        client_id,
        report_type,
        report_period_id,
        created_at DESC
    );

CREATE OR REPLACE FUNCTION cascade_report_jobs_for_period()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM report_generation_jobs
    WHERE client_id = OLD.client_id
      AND report_period_id = OLD.id
      AND report_type = TG_ARGV[0];
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS cascade_social_report_jobs ON report_periods;
CREATE TRIGGER cascade_social_report_jobs
AFTER DELETE ON report_periods
FOR EACH ROW EXECUTE FUNCTION cascade_report_jobs_for_period('social_media');

DROP TRIGGER IF EXISTS cascade_meta_ads_report_jobs ON meta_ads_report_periods;
CREATE TRIGGER cascade_meta_ads_report_jobs
AFTER DELETE ON meta_ads_report_periods
FOR EACH ROW EXECUTE FUNCTION cascade_report_jobs_for_period('meta_ads');

COMMIT;
