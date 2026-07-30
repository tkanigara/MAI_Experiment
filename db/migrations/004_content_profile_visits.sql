ALTER TABLE IF EXISTS social_content_reports
    ADD COLUMN IF NOT EXISTS profile_visits NUMERIC;

ALTER TABLE IF EXISTS competitor_content_reports
    ADD COLUMN IF NOT EXISTS profile_visits NUMERIC;
