BEGIN;

CREATE TABLE IF NOT EXISTS ads_metric_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('meta', 'google_sem', 'google_gdn', 'youtube', 'tiktok')),
    objective_key TEXT NOT NULL,
    metric_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, scope, objective_key),
    CHECK (jsonb_typeof(metric_keys) = 'array')
);

CREATE TABLE IF NOT EXISTS meta_ads_campaign_objective_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    meta_ad_account_id TEXT NOT NULL DEFAULT '',
    campaign_external_id TEXT,
    campaign_key TEXT NOT NULL,
    campaign_name TEXT NOT NULL,
    detected_objective TEXT,
    optimization_goals JSONB NOT NULL DEFAULT '[]'::jsonb,
    result_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggested_objective TEXT,
    suggestion_confidence TEXT,
    reporting_objective TEXT CHECK (reporting_objective IN ('reach', 'engagement', 'views', 'link_clicks', 'leads')),
    is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    is_included BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_meta_campaign_mapping_external
    ON meta_ads_campaign_objective_mappings (client_id, meta_ad_account_id, campaign_external_id)
    WHERE campaign_external_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_meta_campaign_mapping_period
    ON meta_ads_campaign_objective_mappings (meta_ads_report_period_id, campaign_key)
    WHERE campaign_external_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_meta_campaign_mapping_client
    ON meta_ads_campaign_objective_mappings (client_id, is_confirmed, reporting_objective);

ALTER TABLE meta_ads_imports
    ADD COLUMN IF NOT EXISTS schema_version INTEGER NOT NULL DEFAULT 1;

DO $$
DECLARE table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'meta_ads_campaign_performance',
        'meta_ads_adset_performance',
        'meta_ads_ad_performance',
        'meta_ads_placement_breakdown',
        'meta_ads_demographic_breakdown',
        'meta_ads_region_breakdown'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS campaign_objective TEXT', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS optimization_goal TEXT', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS interactions NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS post_shares NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS post_saves NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS post_reactions NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS post_comments NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS video_views NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS thruplay NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS leads NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS destination_clicks NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS profile_visits NUMERIC(28, 4)', table_name);
        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS page_likes NUMERIC(28, 4)', table_name);
    END LOOP;
END $$;

COMMIT;
