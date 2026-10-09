BEGIN;

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

COMMIT;
