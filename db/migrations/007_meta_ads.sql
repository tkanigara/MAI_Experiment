BEGIN;

CREATE TABLE IF NOT EXISTS client_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    product TEXT NOT NULL CHECK (product IN ('social_media', 'meta_ads')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, product)
);

INSERT INTO client_products (client_id, product)
SELECT id, 'social_media'
FROM clients
WHERE NOT EXISTS (SELECT 1 FROM client_products)
ON CONFLICT (client_id, product) DO NOTHING;

CREATE TABLE IF NOT EXISTS meta_ads_report_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_label TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, period_start, period_end),
    CHECK (period_end >= period_start)
);

CREATE TABLE IF NOT EXISTS meta_ads_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    platform TEXT NOT NULL DEFAULT 'meta' CHECK (platform = 'meta'),
    source TEXT NOT NULL DEFAULT 'csv' CHECK (source IN ('csv', 'api')),
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    filenames JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary_totals JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    imported_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, meta_ads_report_period_id, platform)
);

CREATE TABLE IF NOT EXISTS meta_ads_campaign_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    campaign_external_id TEXT,
    campaign_name TEXT NOT NULL,
    source_row_key CHAR(64) NOT NULL,
    source_row_number INTEGER NOT NULL,
    reporting_start DATE NOT NULL,
    reporting_end DATE NOT NULL,
    delivery_status TEXT,
    result_value NUMERIC(28, 8), result_type TEXT, cost_per_result NUMERIC(28, 8),
    budget NUMERIC(28, 4), budget_source TEXT, budget_type TEXT,
    spend NUMERIC(28, 4), impressions NUMERIC(28, 4), reach NUMERIC(28, 4), frequency NUMERIC(20, 8),
    post_engagements NUMERIC(28, 4), link_clicks NUMERIC(28, 4), link_ctr NUMERIC(20, 8),
    instagram_follows NUMERIC(28, 4), page_engagements NUMERIC(28, 4), reaction_reach NUMERIC(20, 8),
    attribution_setting TEXT, start_date DATE, end_value TEXT,
    bid NUMERIC(28, 8), bid_type TEXT, last_significant_edit TIMESTAMPTZ,
    quality_ranking TEXT, engagement_rate_ranking TEXT, conversion_rate_ranking TEXT,
    initial_result_value NUMERIC(28, 8), initial_result_type TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, source_row_key),
    CHECK (reporting_end >= reporting_start)
);

CREATE TABLE IF NOT EXISTS meta_ads_adset_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    campaign_performance_id UUID REFERENCES meta_ads_campaign_performance(id) ON DELETE SET NULL,
    campaign_external_id TEXT, campaign_name TEXT,
    adset_external_id TEXT, adset_name TEXT NOT NULL,
    source_row_key CHAR(64) NOT NULL, source_row_number INTEGER NOT NULL,
    reporting_start DATE NOT NULL, reporting_end DATE NOT NULL, delivery_status TEXT,
    result_value NUMERIC(28, 8), result_type TEXT, cost_per_result NUMERIC(28, 8),
    budget NUMERIC(28, 4), budget_source TEXT, budget_type TEXT,
    spend NUMERIC(28, 4), impressions NUMERIC(28, 4), reach NUMERIC(28, 4), frequency NUMERIC(20, 8),
    post_engagements NUMERIC(28, 4), link_clicks NUMERIC(28, 4), link_ctr NUMERIC(20, 8),
    instagram_follows NUMERIC(28, 4), page_engagements NUMERIC(28, 4), reaction_reach NUMERIC(20, 8),
    attribution_setting TEXT, start_date DATE, end_value TEXT,
    bid NUMERIC(28, 8), bid_type TEXT, last_significant_edit TIMESTAMPTZ,
    quality_ranking TEXT, engagement_rate_ranking TEXT, conversion_rate_ranking TEXT,
    initial_result_value NUMERIC(28, 8), initial_result_type TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, source_row_key),
    CHECK (reporting_end >= reporting_start)
);

CREATE TABLE IF NOT EXISTS meta_ads_ad_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    campaign_performance_id UUID REFERENCES meta_ads_campaign_performance(id) ON DELETE SET NULL,
    adset_performance_id UUID REFERENCES meta_ads_adset_performance(id) ON DELETE SET NULL,
    campaign_external_id TEXT, campaign_name TEXT,
    adset_external_id TEXT, adset_name TEXT NOT NULL,
    ad_external_id TEXT, ad_name TEXT NOT NULL,
    source_row_key CHAR(64) NOT NULL, source_row_number INTEGER NOT NULL,
    reporting_start DATE NOT NULL, reporting_end DATE NOT NULL, delivery_status TEXT,
    result_value NUMERIC(28, 8), result_type TEXT, cost_per_result NUMERIC(28, 8),
    budget NUMERIC(28, 4), budget_source TEXT, budget_type TEXT,
    spend NUMERIC(28, 4), impressions NUMERIC(28, 4), reach NUMERIC(28, 4), frequency NUMERIC(20, 8),
    post_engagements NUMERIC(28, 4), link_clicks NUMERIC(28, 4), link_ctr NUMERIC(20, 8),
    instagram_follows NUMERIC(28, 4), page_engagements NUMERIC(28, 4), reaction_reach NUMERIC(20, 8),
    attribution_setting TEXT, start_date DATE, end_value TEXT,
    bid NUMERIC(28, 8), bid_type TEXT, last_significant_edit TIMESTAMPTZ,
    quality_ranking TEXT, engagement_rate_ranking TEXT, conversion_rate_ranking TEXT,
    initial_result_value NUMERIC(28, 8), initial_result_type TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, source_row_key),
    CHECK (reporting_end >= reporting_start)
);

CREATE TABLE IF NOT EXISTS meta_ads_placement_breakdown (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    ad_performance_id UUID REFERENCES meta_ads_ad_performance(id) ON DELETE SET NULL,
    campaign_external_id TEXT, campaign_name TEXT,
    adset_external_id TEXT, adset_name TEXT NOT NULL,
    ad_external_id TEXT, ad_name TEXT NOT NULL,
    publisher_platform TEXT NOT NULL, placement TEXT NOT NULL, device_platform TEXT NOT NULL,
    source_row_key CHAR(64) NOT NULL, source_row_number INTEGER NOT NULL,
    reporting_start DATE NOT NULL, reporting_end DATE NOT NULL, delivery_status TEXT,
    result_value NUMERIC(28, 8), result_type TEXT, cost_per_result NUMERIC(28, 8),
    budget NUMERIC(28, 4), budget_source TEXT, budget_type TEXT,
    spend NUMERIC(28, 4), impressions NUMERIC(28, 4), reach NUMERIC(28, 4), frequency NUMERIC(20, 8),
    post_engagements NUMERIC(28, 4), link_clicks NUMERIC(28, 4), link_ctr NUMERIC(20, 8),
    instagram_follows NUMERIC(28, 4), page_engagements NUMERIC(28, 4), reaction_reach NUMERIC(20, 8),
    attribution_setting TEXT, start_date DATE, end_value TEXT,
    bid NUMERIC(28, 8), bid_type TEXT, last_significant_edit TIMESTAMPTZ,
    quality_ranking TEXT, engagement_rate_ranking TEXT, conversion_rate_ranking TEXT,
    initial_result_value NUMERIC(28, 8), initial_result_type TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, source_row_key),
    CHECK (reporting_end >= reporting_start)
);

CREATE TABLE IF NOT EXISTS meta_ads_demographic_breakdown (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    ad_performance_id UUID REFERENCES meta_ads_ad_performance(id) ON DELETE SET NULL,
    campaign_external_id TEXT, campaign_name TEXT,
    adset_external_id TEXT, adset_name TEXT NOT NULL,
    ad_external_id TEXT, ad_name TEXT NOT NULL,
    age TEXT NOT NULL, gender TEXT NOT NULL,
    source_row_key CHAR(64) NOT NULL, source_row_number INTEGER NOT NULL,
    reporting_start DATE NOT NULL, reporting_end DATE NOT NULL, delivery_status TEXT,
    result_value NUMERIC(28, 8), result_type TEXT, cost_per_result NUMERIC(28, 8),
    budget NUMERIC(28, 4), budget_source TEXT, budget_type TEXT,
    spend NUMERIC(28, 4), impressions NUMERIC(28, 4), reach NUMERIC(28, 4), frequency NUMERIC(20, 8),
    post_engagements NUMERIC(28, 4), link_clicks NUMERIC(28, 4), link_ctr NUMERIC(20, 8),
    instagram_follows NUMERIC(28, 4), page_engagements NUMERIC(28, 4), reaction_reach NUMERIC(20, 8),
    attribution_setting TEXT, start_date DATE, end_value TEXT,
    bid NUMERIC(28, 8), bid_type TEXT, last_significant_edit TIMESTAMPTZ,
    quality_ranking TEXT, engagement_rate_ranking TEXT, conversion_rate_ranking TEXT,
    initial_result_value NUMERIC(28, 8), initial_result_type TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, source_row_key),
    CHECK (reporting_end >= reporting_start)
);

CREATE TABLE IF NOT EXISTS meta_ads_region_breakdown (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    ad_performance_id UUID REFERENCES meta_ads_ad_performance(id) ON DELETE SET NULL,
    campaign_external_id TEXT, campaign_name TEXT,
    adset_external_id TEXT, adset_name TEXT NOT NULL,
    ad_external_id TEXT, ad_name TEXT NOT NULL,
    region TEXT NOT NULL,
    source_row_key CHAR(64) NOT NULL, source_row_number INTEGER NOT NULL,
    reporting_start DATE NOT NULL, reporting_end DATE NOT NULL, delivery_status TEXT,
    result_value NUMERIC(28, 8), result_type TEXT, cost_per_result NUMERIC(28, 8),
    budget NUMERIC(28, 4), budget_source TEXT, budget_type TEXT,
    spend NUMERIC(28, 4), impressions NUMERIC(28, 4), reach NUMERIC(28, 4), frequency NUMERIC(20, 8),
    post_engagements NUMERIC(28, 4), link_clicks NUMERIC(28, 4), link_ctr NUMERIC(20, 8),
    instagram_follows NUMERIC(28, 4), page_engagements NUMERIC(28, 4), reaction_reach NUMERIC(20, 8),
    attribution_setting TEXT, start_date DATE, end_value TEXT,
    bid NUMERIC(28, 8), bid_type TEXT, last_significant_edit TIMESTAMPTZ,
    quality_ranking TEXT, engagement_rate_ranking TEXT, conversion_rate_ranking TEXT,
    initial_result_value NUMERIC(28, 8), initial_result_type TEXT,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, source_row_key),
    CHECK (reporting_end >= reporting_start)
);

CREATE INDEX IF NOT EXISTS idx_meta_ads_imports_period
    ON meta_ads_imports (client_id, meta_ads_report_period_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign_period
    ON meta_ads_campaign_performance (client_id, meta_ads_report_period_id, campaign_name);
CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign_external
    ON meta_ads_campaign_performance (campaign_external_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_adset_period
    ON meta_ads_adset_performance (client_id, meta_ads_report_period_id, adset_name);
CREATE INDEX IF NOT EXISTS idx_meta_ads_adset_external
    ON meta_ads_adset_performance (adset_external_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_ad_period
    ON meta_ads_ad_performance (client_id, meta_ads_report_period_id, adset_name, ad_name);
CREATE INDEX IF NOT EXISTS idx_meta_ads_ad_external
    ON meta_ads_ad_performance (ad_external_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_placement_period
    ON meta_ads_placement_breakdown (client_id, meta_ads_report_period_id, publisher_platform, placement);
CREATE INDEX IF NOT EXISTS idx_meta_ads_demographic_period
    ON meta_ads_demographic_breakdown (client_id, meta_ads_report_period_id, age, gender);
CREATE INDEX IF NOT EXISTS idx_meta_ads_region_period
    ON meta_ads_region_breakdown (client_id, meta_ads_report_period_id, region);

CREATE INDEX IF NOT EXISTS idx_client_products_product
    ON client_products (product, is_active, client_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_report_periods_client
    ON meta_ads_report_periods (client_id, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign_raw_data_gin
    ON meta_ads_campaign_performance USING GIN (raw_data);
CREATE INDEX IF NOT EXISTS idx_meta_ads_ad_raw_data_gin
    ON meta_ads_ad_performance USING GIN (raw_data);

COMMIT;
