CREATE TABLE IF NOT EXISTS report_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    report_period_id UUID NOT NULL REFERENCES report_periods(id) ON DELETE CASCADE,
    source_report_period_id UUID REFERENCES report_periods(id) ON DELETE CASCADE,
    platform TEXT CHECK (
        platform IS NULL
        OR platform IN ('instagram', 'facebook', 'tiktok', 'youtube')
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

ALTER TABLE report_overrides
    ADD COLUMN IF NOT EXISTS source_report_period_id UUID
    REFERENCES report_periods(id) ON DELETE CASCADE;

UPDATE report_overrides
SET source_report_period_id = report_period_id
WHERE source_report_period_id IS NULL;

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

CREATE INDEX IF NOT EXISTS idx_report_overrides_period_section
    ON report_overrides (report_period_id, section_key, is_active);
CREATE INDEX IF NOT EXISTS idx_report_overrides_entity
    ON report_overrides (entity_type, entity_ref, override_key, is_active);
CREATE INDEX IF NOT EXISTS idx_report_edit_history_period
    ON report_edit_history (report_period_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_assets_period
    ON report_assets (report_period_id, created_at DESC);
