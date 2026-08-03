BEGIN;

ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS has_linkedin BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_threads BOOLEAN NOT NULL DEFAULT FALSE;

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

CREATE INDEX IF NOT EXISTS idx_linkedin_reports_period
    ON linkedin_reports (client_id, report_period_id);
CREATE INDEX IF NOT EXISTS idx_threads_reports_period
    ON threads_reports (client_id, report_period_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_reports_raw_sections_gin
    ON linkedin_reports USING GIN (raw_sections);
CREATE INDEX IF NOT EXISTS idx_threads_reports_raw_sections_gin
    ON threads_reports USING GIN (raw_sections);

ALTER TABLE client_social_profiles DROP CONSTRAINT IF EXISTS client_social_profiles_platform_check;
ALTER TABLE client_social_profiles ADD CONSTRAINT client_social_profiles_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE competitor_social_profiles DROP CONSTRAINT IF EXISTS competitor_social_profiles_platform_check;
ALTER TABLE competitor_social_profiles ADD CONSTRAINT competitor_social_profiles_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE etl_runs DROP CONSTRAINT IF EXISTS etl_runs_platform_check;
ALTER TABLE etl_runs ADD CONSTRAINT etl_runs_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE raw_api_responses DROP CONSTRAINT IF EXISTS raw_api_responses_platform_check;
ALTER TABLE raw_api_responses ADD CONSTRAINT raw_api_responses_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE kpi_targets DROP CONSTRAINT IF EXISTS kpi_targets_platform_check;
ALTER TABLE kpi_targets ADD CONSTRAINT kpi_targets_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE kpi_results DROP CONSTRAINT IF EXISTS kpi_results_platform_check;
ALTER TABLE kpi_results ADD CONSTRAINT kpi_results_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE competitor_profile_reports DROP CONSTRAINT IF EXISTS competitor_profile_reports_platform_check;
ALTER TABLE competitor_profile_reports ADD CONSTRAINT competitor_profile_reports_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE competitor_content_reports DROP CONSTRAINT IF EXISTS competitor_content_reports_platform_check;
ALTER TABLE competitor_content_reports ADD CONSTRAINT competitor_content_reports_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE social_content_reports DROP CONSTRAINT IF EXISTS social_content_reports_platform_check;
ALTER TABLE social_content_reports ADD CONSTRAINT social_content_reports_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE report_insights DROP CONSTRAINT IF EXISTS report_insights_platform_check;
ALTER TABLE report_insights ADD CONSTRAINT report_insights_platform_check
    CHECK (platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

ALTER TABLE report_overrides DROP CONSTRAINT IF EXISTS report_overrides_platform_check;
ALTER TABLE report_overrides ADD CONSTRAINT report_overrides_platform_check
    CHECK (platform IS NULL OR platform IN ('instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'threads'));

COMMIT;
