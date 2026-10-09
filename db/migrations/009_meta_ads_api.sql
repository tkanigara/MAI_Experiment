BEGIN;

CREATE TABLE IF NOT EXISTS client_meta_ad_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    ad_account_id TEXT NOT NULL,
    account_name TEXT,
    account_status INTEGER,
    currency TEXT,
    timezone_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, ad_account_id)
);

ALTER TABLE meta_ads_imports
    ADD COLUMN IF NOT EXISTS selected_ad_account_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS platform_scope JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS sync_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sync_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS row_counts JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
DECLARE constraint_name TEXT;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'meta_ads_imports'::regclass
      AND contype = 'u'
      AND pg_get_constraintdef(oid) LIKE '%(client_id, meta_ads_report_period_id, platform)%'
    LIMIT 1;
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE meta_ads_imports DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS meta_ads_active_snapshots (
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook')),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_ads_report_period_id, platform)
);

UPDATE meta_ads_imports
SET platform_scope = '["instagram", "facebook"]'::jsonb
WHERE source = 'csv' AND platform_scope = '[]'::jsonb;

ALTER TABLE meta_ads_campaign_performance ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_adset_performance ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_ad_performance ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_placement_breakdown ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_demographic_breakdown ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_region_breakdown ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;

CREATE TABLE IF NOT EXISTS meta_ads_creatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    meta_ad_account_id TEXT NOT NULL,
    campaign_external_id TEXT,
    adset_external_id TEXT,
    ad_external_id TEXT NOT NULL,
    creative_external_id TEXT,
    creative_name TEXT,
    thumbnail_url TEXT,
    image_url TEXT,
    preview_url TEXT,
    permalink_url TEXT,
    effective_object_story_id TEXT,
    page_id TEXT,
    instagram_actor_id TEXT,
    creative_fetched_at TIMESTAMPTZ,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, meta_ad_account_id, ad_external_id)
);

-- Existing CSV imports become the active source for both Meta platforms.
INSERT INTO meta_ads_active_snapshots (meta_ads_report_period_id, platform, import_id)
SELECT DISTINCT ON (i.meta_ads_report_period_id, platform_name)
       i.meta_ads_report_period_id, platform_name, i.id
FROM meta_ads_imports i
CROSS JOIN (VALUES ('instagram'), ('facebook')) AS platforms(platform_name)
WHERE i.status = 'success'
ORDER BY i.meta_ads_report_period_id, platform_name, COALESCE(i.imported_at, i.created_at) DESC
ON CONFLICT (meta_ads_report_period_id, platform) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_client_meta_ad_accounts_client
    ON client_meta_ad_accounts (client_id, is_active, ad_account_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_import_history
    ON meta_ads_imports (client_id, meta_ads_report_period_id, source, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meta_ads_creatives_import_ad
    ON meta_ads_creatives (import_id, ad_external_id);

COMMIT;
