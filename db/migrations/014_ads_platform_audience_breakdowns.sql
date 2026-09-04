ALTER TABLE meta_ads_demographic_breakdown
    ADD COLUMN IF NOT EXISTS publisher_platform TEXT;

ALTER TABLE meta_ads_region_breakdown
    ADD COLUMN IF NOT EXISTS publisher_platform TEXT;

CREATE INDEX IF NOT EXISTS idx_meta_ads_demographic_platform
    ON meta_ads_demographic_breakdown
        (client_id, meta_ads_report_period_id, publisher_platform, age, gender);

CREATE INDEX IF NOT EXISTS idx_meta_ads_region_platform
    ON meta_ads_region_breakdown
        (client_id, meta_ads_report_period_id, publisher_platform, region);
