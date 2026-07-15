CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_code TEXT NOT NULL UNIQUE,
    client_name TEXT NOT NULL,
    industry TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    has_instagram BOOLEAN NOT NULL DEFAULT FALSE,
    has_facebook BOOLEAN NOT NULL DEFAULT FALSE,
    has_tiktok BOOLEAN NOT NULL DEFAULT FALSE,
    has_youtube BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_social_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    source_profile_id TEXT NOT NULL,
    profile_name TEXT,
    profile_url TEXT,
    image_url TEXT,
    is_competitor BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    raw_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, platform, source_profile_id)
);

CREATE TABLE IF NOT EXISTS client_competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    competitor_name TEXT NOT NULL,
    industry TEXT,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, competitor_name)
);

CREATE TABLE IF NOT EXISTS competitor_social_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id UUID NOT NULL REFERENCES client_competitors(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    source_profile_id TEXT,
    profile_name TEXT NOT NULL,
    profile_url TEXT,
    image_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    raw_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (competitor_id, platform, source_profile_id)
);

CREATE TABLE IF NOT EXISTS report_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, period_start, period_end),
    CHECK (period_end >= period_start)
);

CREATE TABLE IF NOT EXISTS etl_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    report_period_id UUID REFERENCES report_periods(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    platform TEXT CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_api_responses (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES etl_runs(id) ON DELETE SET NULL,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    platform TEXT CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    endpoint TEXT NOT NULL,
    request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    response JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kpi_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    metric_name TEXT NOT NULL,
    period_year INTEGER NOT NULL,
    period_month INTEGER NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    target_month NUMERIC,
    target_year NUMERIC,
    unit TEXT,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, platform, metric_name, period_year, period_month)
);

CREATE TABLE IF NOT EXISTS kpi_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    kpi_target_id UUID REFERENCES kpi_targets(id) ON DELETE SET NULL,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    metric_name TEXT NOT NULL,
    metric_category TEXT,
    actual_month NUMERIC,
    actual_year NUMERIC,
    target_month NUMERIC,
    target_year NUMERIC,
    achievement_month NUMERIC,
    achievement_year NUMERIC,
    unit TEXT,
    source_report_table TEXT,
    source_report_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, platform, report_period_id, metric_name)
);

CREATE TABLE IF NOT EXISTS competitor_profile_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    competitor_id UUID REFERENCES client_competitors(id) ON DELETE SET NULL,
    competitor_profile_id UUID REFERENCES competitor_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    profile_name TEXT NOT NULL,
    total_followers NUMERIC,
    follower_growth NUMERIC,
    follower_growth_rate NUMERIC,
    total_posts NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    reach NUMERIC,
    impressions NUMERIC,
    ranking_followers INTEGER,
    ranking_growth INTEGER,
    ranking_posts INTEGER,
    ranking_engagement INTEGER,
    ranking_engagement_rate INTEGER,
    profile_url TEXT,
    image_url TEXT,
    raw_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, platform, report_period_id, profile_name)
);

CREATE TABLE IF NOT EXISTS competitor_content_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    competitor_id UUID REFERENCES client_competitors(id) ON DELETE SET NULL,
    competitor_profile_id UUID REFERENCES competitor_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    profile_name TEXT NOT NULL,
    post_id TEXT,
    published_at TIMESTAMPTZ,
    caption TEXT,
    permalink TEXT,
    image_url TEXT,
    content_type TEXT,
    content_rank INTEGER,
    performance_bucket TEXT CHECK (
        performance_bucket IN ('top', 'low', 'best_competitor', 'flop_competitor')
    ),
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    saves NUMERIC,
    reposts NUMERIC,
    reactions NUMERIC,
    views NUMERIC,
    reach NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    raw_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, platform, report_period_id, profile_name, post_id)
);

CREATE TABLE IF NOT EXISTS social_content_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    post_id TEXT,
    published_at TIMESTAMPTZ,
    caption TEXT,
    permalink TEXT,
    image_url TEXT,
    content_type TEXT,
    content_rank INTEGER,
    performance_bucket TEXT CHECK (performance_bucket IN ('all', 'top', 'low')),
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    saves NUMERIC,
    reposts NUMERIC,
    reactions NUMERIC,
    views NUMERIC,
    reach NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    audience_demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, platform, report_period_id, performance_bucket, post_id)
);

CREATE TABLE IF NOT EXISTS report_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    report_period_id UUID REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube')),
    section_key TEXT NOT NULL,
    insight_key TEXT NOT NULL,
    insight_text TEXT NOT NULL,
    display_order INTEGER,
    source TEXT NOT NULL DEFAULT 'manual',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, report_period_id, platform, section_key, insight_key)
);

CREATE TABLE IF NOT EXISTS instagram_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    total_followers NUMERIC,
    follower_growth NUMERIC,
    follower_growth_rate NUMERIC,
    follows NUMERIC,
    unfollows NUMERIC,
    reach NUMERIC,
    impressions NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    saves NUMERIC,
    reposts NUMERIC,
    total_posts NUMERIC,
    reels_posts NUMERIC,
    carousel_posts NUMERIC,
    single_posts NUMERIC,
    story_posts NUMERIC,
    posts_per_day NUMERIC,
    post_interaction_rate NUMERIC,
    page_performance_index NUMERIC,
    demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_followers JSONB NOT NULL DEFAULT '[]'::jsonb,
    daily_engagement JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    low_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_words JSONB NOT NULL DEFAULT '[]'::jsonb,
    best_times_to_post JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_type_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    competitor_profiles JSONB NOT NULL DEFAULT '[]'::jsonb,
    competitor_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_sections JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, profile_id, report_period_id)
);

CREATE TABLE IF NOT EXISTS facebook_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    total_followers NUMERIC,
    follower_growth NUMERIC,
    follower_growth_rate NUMERIC,
    follows NUMERIC,
    unfollows NUMERIC,
    reach NUMERIC,
    impressions NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    reactions NUMERIC,
    total_posts NUMERIC,
    reels_posts NUMERIC,
    carousel_posts NUMERIC,
    single_posts NUMERIC,
    story_posts NUMERIC,
    posts_per_day NUMERIC,
    post_interaction_rate NUMERIC,
    page_performance_index NUMERIC,
    demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_followers JSONB NOT NULL DEFAULT '[]'::jsonb,
    daily_engagement JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    low_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_words JSONB NOT NULL DEFAULT '[]'::jsonb,
    best_times_to_post JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_type_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    competitor_profiles JSONB NOT NULL DEFAULT '[]'::jsonb,
    competitor_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_sections JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, profile_id, report_period_id)
);

CREATE TABLE IF NOT EXISTS tiktok_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    total_followers NUMERIC,
    follower_growth NUMERIC,
    follower_growth_rate NUMERIC,
    follows NUMERIC,
    unfollows NUMERIC,
    total_views NUMERIC,
    reach NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    saves NUMERIC,
    total_posts NUMERIC,
    video_posts NUMERIC,
    posts_per_day NUMERIC,
    post_interaction_rate NUMERIC,
    page_performance_index NUMERIC,
    demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_followers JSONB NOT NULL DEFAULT '[]'::jsonb,
    daily_engagement JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    low_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_words JSONB NOT NULL DEFAULT '[]'::jsonb,
    best_times_to_post JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_type_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    competitor_profiles JSONB NOT NULL DEFAULT '[]'::jsonb,
    competitor_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_sections JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, profile_id, report_period_id)
);

CREATE TABLE IF NOT EXISTS youtube_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES client_social_profiles(id) ON DELETE SET NULL,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'fanpage_karma',
    total_subscribers NUMERIC,
    subscriber_growth NUMERIC,
    subscriber_growth_rate NUMERIC,
    subscribers_lost NUMERIC,
    total_views NUMERIC,
    reach NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    total_posts NUMERIC,
    video_posts NUMERIC,
    shorts_posts NUMERIC,
    long_form_posts NUMERIC,
    live_posts NUMERIC,
    posts_per_day NUMERIC,
    post_interaction_rate NUMERIC,
    page_performance_index NUMERIC,
    demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_subscribers JSONB NOT NULL DEFAULT '[]'::jsonb,
    daily_views JSONB NOT NULL DEFAULT '[]'::jsonb,
    daily_engagement JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    low_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_hashtags JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_words JSONB NOT NULL DEFAULT '[]'::jsonb,
    best_times_to_post JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_type_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    competitor_profiles JSONB NOT NULL DEFAULT '[]'::jsonb,
    competitor_posts JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_sections JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, profile_id, report_period_id)
);

CREATE INDEX IF NOT EXISTS idx_client_social_profiles_client_platform
    ON client_social_profiles (client_id, platform);

ALTER TABLE IF EXISTS tiktok_reports
    ADD COLUMN IF NOT EXISTS content_type_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS youtube_reports
    ADD COLUMN IF NOT EXISTS content_type_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS facebook_reports
    ADD COLUMN IF NOT EXISTS demographics JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS youtube_reports
    ADD COLUMN IF NOT EXISTS demographics JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE IF EXISTS youtube_reports
    ADD COLUMN IF NOT EXISTS subscribers_lost NUMERIC;

ALTER TABLE IF EXISTS youtube_reports
    ADD COLUMN IF NOT EXISTS reach NUMERIC;

ALTER TABLE IF EXISTS youtube_reports
    ADD COLUMN IF NOT EXISTS long_form_posts NUMERIC;

ALTER TABLE IF EXISTS youtube_reports
    ADD COLUMN IF NOT EXISTS live_posts NUMERIC;

ALTER TABLE IF EXISTS social_content_reports
    DROP CONSTRAINT IF EXISTS social_content_reports_client_id_platform_report_period_id_post_id_key;

ALTER TABLE IF EXISTS social_content_reports
    DROP CONSTRAINT IF EXISTS social_content_reports_client_id_platform_report_period_id__key;

ALTER TABLE IF EXISTS social_content_reports
    DROP CONSTRAINT IF EXISTS social_content_reports_performance_bucket_check;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'social_content_reports_performance_bucket_check'
    ) THEN
        ALTER TABLE social_content_reports
            ADD CONSTRAINT social_content_reports_performance_bucket_check
            CHECK (performance_bucket IN ('all', 'top', 'low'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'social_content_reports_unique_bucket_post'
    ) THEN
        ALTER TABLE social_content_reports
            ADD CONSTRAINT social_content_reports_unique_bucket_post
            UNIQUE (client_id, platform, report_period_id, performance_bucket, post_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_client_competitors_client
    ON client_competitors (client_id, is_active);

CREATE INDEX IF NOT EXISTS idx_competitor_social_profiles_lookup
    ON competitor_social_profiles (competitor_id, platform, is_active);

CREATE INDEX IF NOT EXISTS idx_report_periods_client_period
    ON report_periods (client_id, period_start, period_end);

CREATE INDEX IF NOT EXISTS idx_raw_api_responses_lookup
    ON raw_api_responses (source, platform, endpoint, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_api_responses_response_gin
    ON raw_api_responses USING GIN (response);

CREATE INDEX IF NOT EXISTS idx_kpi_targets_lookup
    ON kpi_targets (client_id, platform, period_year, period_month, metric_name);

CREATE INDEX IF NOT EXISTS idx_kpi_results_dashboard
    ON kpi_results (client_id, platform, report_period_id, metric_name);

CREATE INDEX IF NOT EXISTS idx_kpi_results_target
    ON kpi_results (kpi_target_id);

CREATE INDEX IF NOT EXISTS idx_competitor_profile_reports_dashboard
    ON competitor_profile_reports (client_id, platform, report_period_id);

CREATE INDEX IF NOT EXISTS idx_competitor_profile_reports_engagement
    ON competitor_profile_reports (
        client_id,
        platform,
        report_period_id,
        total_engagement DESC
    );

CREATE INDEX IF NOT EXISTS idx_competitor_content_reports_dashboard
    ON competitor_content_reports (
        client_id,
        platform,
        report_period_id,
        performance_bucket,
        content_rank
    );

CREATE INDEX IF NOT EXISTS idx_competitor_content_reports_engagement
    ON competitor_content_reports (
        client_id,
        platform,
        report_period_id,
        total_engagement DESC
    );

CREATE INDEX IF NOT EXISTS idx_competitor_content_reports_raw_metrics_gin
    ON competitor_content_reports USING GIN (raw_metrics);

CREATE INDEX IF NOT EXISTS idx_social_content_reports_dashboard
    ON social_content_reports (
        client_id,
        platform,
        report_period_id,
        performance_bucket,
        content_rank
    );

CREATE INDEX IF NOT EXISTS idx_social_content_reports_engagement
    ON social_content_reports (
        client_id,
        platform,
        report_period_id,
        total_engagement DESC
    );

CREATE INDEX IF NOT EXISTS idx_social_content_reports_raw_metrics_gin
    ON social_content_reports USING GIN (raw_metrics);

CREATE INDEX IF NOT EXISTS idx_report_insights_lookup
    ON report_insights (
        client_id,
        report_period_id,
        platform,
        section_key,
        display_order
    );

CREATE INDEX IF NOT EXISTS idx_instagram_reports_period
    ON instagram_reports (client_id, report_period_id);

CREATE INDEX IF NOT EXISTS idx_facebook_reports_period
    ON facebook_reports (client_id, report_period_id);

CREATE INDEX IF NOT EXISTS idx_tiktok_reports_period
    ON tiktok_reports (client_id, report_period_id);

CREATE INDEX IF NOT EXISTS idx_youtube_reports_period
    ON youtube_reports (client_id, report_period_id);

CREATE INDEX IF NOT EXISTS idx_instagram_reports_raw_sections_gin
    ON instagram_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_facebook_reports_raw_sections_gin
    ON facebook_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_tiktok_reports_raw_sections_gin
    ON tiktok_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_youtube_reports_raw_sections_gin
    ON youtube_reports USING GIN (raw_sections);
