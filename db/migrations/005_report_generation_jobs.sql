BEGIN;

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

COMMIT;
