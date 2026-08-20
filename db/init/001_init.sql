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
    has_linkedin BOOLEAN NOT NULL DEFAULT FALSE,
    has_threads BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_social_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    platform TEXT CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    platform TEXT CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
    endpoint TEXT NOT NULL,
    request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    response JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kpi_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    profile_visits NUMERIC,
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
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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
    profile_visits NUMERIC,
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
    platform TEXT CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')),
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

CREATE TABLE IF NOT EXISTS linkedin_reports (
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
    impressions NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    saves NUMERIC,
    reposts NUMERIC,
    reactions NUMERIC,
    total_posts NUMERIC,
    photo_posts NUMERIC,
    video_posts NUMERIC,
    text_posts NUMERIC,
    posts_per_day NUMERIC,
    post_interaction_rate NUMERIC,
    page_performance_index NUMERIC,
    demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_followers JSONB NOT NULL DEFAULT '[]'::jsonb,
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

CREATE TABLE IF NOT EXISTS threads_reports (
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
    impressions NUMERIC,
    total_engagement NUMERIC,
    engagement_rate NUMERIC,
    likes NUMERIC,
    comments NUMERIC,
    shares NUMERIC,
    saves NUMERIC,
    reposts NUMERIC,
    reactions NUMERIC,
    total_posts NUMERIC,
    photo_posts NUMERIC,
    video_posts NUMERIC,
    text_posts NUMERIC,
    posts_per_day NUMERIC,
    post_interaction_rate NUMERIC,
    page_performance_index NUMERIC,
    demographics JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_followers JSONB NOT NULL DEFAULT '[]'::jsonb,
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

CREATE TABLE IF NOT EXISTS report_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    source_report_period_id UUID REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT CHECK (
        platform IS NULL
        OR platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads')
    ),
    scope TEXT NOT NULL CHECK (scope IN ('field', 'derived', 'placeholder')),
    section_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    override_key TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'text',
    source_value JSONB,
    override_value JSONB NOT NULL,
    source_updated_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    edited_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (report_period_id, scope, entity_ref, override_key)
);

CREATE TABLE IF NOT EXISTS report_edit_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    override_id UUID REFERENCES report_overrides(id) ON DELETE SET NULL,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT,
    section_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    field_key TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('update', 'restore')),
    old_value JSONB,
    new_value JSONB,
    edited_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS report_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT,
    object_name TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 6000000),
    public_url TEXT NOT NULL,
    uploaded_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS report_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    retry_of_job_id UUID REFERENCES report_generation_jobs(id) ON DELETE SET NULL,
    client_name_snapshot TEXT NOT NULL,
    period_label_snapshot TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (
        status IN (
            'queued',
            'running',
            'retrying',
            'cancel_requested',
            'completed',
            'failed',
            'cancelled'
        )
    ),
    current_stage TEXT NOT NULL DEFAULT 'queued',
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    requested_by TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    cloud_task_name TEXT UNIQUE,
    source_data_version TEXT,
    analysis_cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    presentation_id TEXT,
    presentation_url TEXT,
    report_name TEXT,
    gemini_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code TEXT,
    error_message TEXT,
    cancel_reason TEXT,
    cancelled_by TEXT,
    cancel_requested_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (attempt_count <= max_attempts),
    CHECK (
        finished_at IS NULL
        OR started_at IS NULL
        OR finished_at >= started_at
    )
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
    ADD COLUMN IF NOT EXISTS profile_visits NUMERIC;

ALTER TABLE IF EXISTS competitor_content_reports
    ADD COLUMN IF NOT EXISTS profile_visits NUMERIC;

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

CREATE INDEX IF NOT EXISTS idx_linkedin_reports_period
    ON linkedin_reports (client_id, report_period_id);

CREATE INDEX IF NOT EXISTS idx_threads_reports_period
    ON threads_reports (client_id, report_period_id);

CREATE INDEX IF NOT EXISTS idx_instagram_reports_raw_sections_gin
    ON instagram_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_facebook_reports_raw_sections_gin
    ON facebook_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_tiktok_reports_raw_sections_gin
    ON tiktok_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_youtube_reports_raw_sections_gin
    ON youtube_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_linkedin_reports_raw_sections_gin
    ON linkedin_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_threads_reports_raw_sections_gin
    ON threads_reports USING GIN (raw_sections);

CREATE INDEX IF NOT EXISTS idx_report_overrides_period_section
    ON report_overrides (report_period_id, section_key, is_active);

CREATE INDEX IF NOT EXISTS idx_report_overrides_entity
    ON report_overrides (entity_type, entity_ref, override_key, is_active);

CREATE INDEX IF NOT EXISTS idx_report_edit_history_period
    ON report_edit_history (report_period_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_report_assets_period
    ON report_assets (report_period_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_report_generation_jobs_active_period
    ON report_generation_jobs (client_id, report_period_id)
    WHERE status IN ('queued', 'running', 'retrying', 'cancel_requested');

CREATE INDEX IF NOT EXISTS idx_report_generation_jobs_period_history
    ON report_generation_jobs (
        client_id,
        report_period_id,
        created_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_report_generation_jobs_queue
    ON report_generation_jobs (status, queued_at)
    WHERE status IN ('queued', 'retrying');

CREATE INDEX IF NOT EXISTS idx_report_generation_jobs_retry
    ON report_generation_jobs (retry_of_job_id)
    WHERE retry_of_job_id IS NOT NULL;

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
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
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
    date_preset TEXT,
    data_start DATE,
    data_end DATE,
    imported_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, meta_ads_report_period_id, platform),
    CHECK (data_start IS NULL OR data_end IS NULL OR data_end >= data_start)
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

-- Meta Ads API account mapping, append-only snapshots, and creative metadata.
CREATE TABLE IF NOT EXISTS client_meta_ad_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    ad_account_id TEXT NOT NULL, account_name TEXT, account_status INTEGER, currency TEXT, timezone_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, ad_account_id)
);
ALTER TABLE meta_ads_imports ADD COLUMN IF NOT EXISTS selected_ad_account_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE meta_ads_imports ADD COLUMN IF NOT EXISTS platform_scope JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE meta_ads_imports ADD COLUMN IF NOT EXISTS sync_started_at TIMESTAMPTZ;
ALTER TABLE meta_ads_imports ADD COLUMN IF NOT EXISTS sync_completed_at TIMESTAMPTZ;
ALTER TABLE meta_ads_imports ADD COLUMN IF NOT EXISTS row_counts JSONB NOT NULL DEFAULT '{}'::jsonb;
DO $$ DECLARE constraint_name TEXT; BEGIN
    SELECT conname INTO constraint_name FROM pg_constraint WHERE conrelid = 'meta_ads_imports'::regclass AND contype = 'u'
      AND pg_get_constraintdef(oid) LIKE '%(client_id, meta_ads_report_period_id, platform)%' LIMIT 1;
    IF constraint_name IS NOT NULL THEN EXECUTE format('ALTER TABLE meta_ads_imports DROP CONSTRAINT %I', constraint_name); END IF;
END $$;
CREATE TABLE IF NOT EXISTS meta_ads_active_snapshots (
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook')),
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (meta_ads_report_period_id, platform)
);
UPDATE meta_ads_imports SET platform_scope='["instagram", "facebook"]'::jsonb
WHERE source='csv' AND platform_scope='[]'::jsonb;
ALTER TABLE meta_ads_campaign_performance ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_adset_performance ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_ad_performance ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_placement_breakdown ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_demographic_breakdown ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
ALTER TABLE meta_ads_region_breakdown ADD COLUMN IF NOT EXISTS meta_ad_account_id TEXT;
CREATE TABLE IF NOT EXISTS meta_ads_creatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    meta_ad_account_id TEXT NOT NULL, campaign_external_id TEXT, adset_external_id TEXT, ad_external_id TEXT NOT NULL,
    creative_external_id TEXT, creative_name TEXT, thumbnail_url TEXT, image_url TEXT, preview_url TEXT, permalink_url TEXT,
    effective_object_story_id TEXT, page_id TEXT, instagram_actor_id TEXT, creative_fetched_at TIMESTAMPTZ,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, meta_ad_account_id, ad_external_id)
);
INSERT INTO meta_ads_active_snapshots (meta_ads_report_period_id, platform, import_id)
SELECT DISTINCT ON (i.meta_ads_report_period_id, platform_name) i.meta_ads_report_period_id, platform_name, i.id
FROM meta_ads_imports i CROSS JOIN (VALUES ('instagram'), ('facebook')) AS platforms(platform_name)
WHERE i.status = 'success' ORDER BY i.meta_ads_report_period_id, platform_name, COALESCE(i.imported_at, i.created_at) DESC
ON CONFLICT (meta_ads_report_period_id, platform) DO NOTHING;

-- Ads objective mapping, configurable metrics, and canonical API fields.
-- Keep the bootstrap schema aligned with migration 010 so a fresh Docker
-- volume is immediately usable without a separate manual migration step.
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

CREATE TABLE IF NOT EXISTS meta_ads_data_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('campaign', 'adset', 'ad', 'placement')),
    entity_row_id UUID NOT NULL,
    field_key TEXT NOT NULL,
    source_value JSONB,
    override_value JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    edited_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, entity_type, entity_row_id, field_key)
);

CREATE TABLE IF NOT EXISTS meta_ads_data_edit_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    override_id UUID REFERENCES meta_ads_data_overrides(id) ON DELETE SET NULL,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meta_ads_report_period_id UUID NOT NULL REFERENCES meta_ads_report_periods(id) ON DELETE CASCADE,
    import_id UUID NOT NULL REFERENCES meta_ads_imports(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_row_id UUID NOT NULL,
    entity_label TEXT,
    field_key TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('update', 'restore')),
    old_value JSONB,
    new_value JSONB,
    edited_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_meta_ads_data_overrides_snapshot
    ON meta_ads_data_overrides (import_id, entity_type, is_active);
CREATE INDEX IF NOT EXISTS idx_meta_ads_data_overrides_period
    ON meta_ads_data_overrides (meta_ads_report_period_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_meta_ads_data_edit_history_period
    ON meta_ads_data_edit_history (meta_ads_report_period_id, created_at DESC);

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
