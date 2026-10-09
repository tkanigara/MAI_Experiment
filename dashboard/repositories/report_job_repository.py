from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

try:
    from dashboard.db import create_db_engine
    from dashboard.repositories.report_data_lock import (
        ACTIVE_JOB_STATUSES,
        ReportDataLockedError,
        lock_report_period,
    )
except ModuleNotFoundError:
    from db import create_db_engine
    from repositories.report_data_lock import (
        ACTIVE_JOB_STATUSES,
        ReportDataLockedError,
        lock_report_period,
    )


TERMINAL_JOB_STATUSES = ("completed", "failed", "cancelled")
ADS_REPORT_TYPES = {"ads", "meta_ads", "paid_ads"}


def _normalize_report_type(value: Any) -> str:
    normalized = str(value or "social_media").strip().lower()
    return "meta_ads" if normalized in ADS_REPORT_TYPES else "social_media"


class ReportJobNotFoundError(ValueError):
    pass


class ActiveReportJobError(ValueError):
    def __init__(self, job: dict):
        self.job = job
        super().__init__(
            "An active report generation job already exists for this period."
        )


class ReportJobTransitionError(RuntimeError):
    def __init__(self, job: dict, target_status: str):
        self.job = job
        self.target_status = target_status
        super().__init__(
            f"Report job cannot transition from "
            f"{job.get('status')!r} to {target_status!r}."
        )


def _row_dict(row) -> dict | None:
    return dict(row) if row is not None else None


def _json_parameter(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


class ReportJobRepository:
    def __init__(self, engine=None):
        self.engine = engine or create_db_engine()

    @staticmethod
    def _context(
        conn,
        client_id: str,
        period_id: str,
        report_type: str = "social_media",
    ) -> dict:
        period_table = (
            "meta_ads_report_periods"
            if _normalize_report_type(report_type) == "meta_ads"
            else "report_periods"
        )
        row = conn.execute(
            text(
                f"""
                SELECT
                    c.id AS client_id,
                    c.client_name,
                    rp.id AS report_period_id,
                    COALESCE(
                        NULLIF(rp.period_label, ''),
                        to_char(rp.period_start, 'FMMonth YYYY')
                    ) AS period_label
                FROM clients c
                JOIN {period_table} rp ON rp.client_id = c.id
                WHERE c.id = :client_id
                  AND rp.id = :period_id
                """
            ),
            {"client_id": client_id, "period_id": period_id},
        ).mappings().first()
        if not row:
            raise ValueError("Client or report period not found.")
        return dict(row)

    @staticmethod
    def _lock_ads_period(conn, client_id: str, period_id: str) -> dict:
        period = conn.execute(
            text(
                """
                SELECT id, client_id, period_label, period_start
                FROM meta_ads_report_periods
                WHERE id = CAST(:period_id AS UUID)
                  AND client_id = CAST(:client_id AS UUID)
                FOR UPDATE
                """
            ),
            {"client_id": client_id, "period_id": period_id},
        ).mappings().first()
        if not period:
            raise ValueError("Ads report month not found")

        active = conn.execute(
            text(
                """
                SELECT *
                FROM report_generation_jobs
                WHERE client_id = CAST(:client_id AS UUID)
                  AND report_period_id = CAST(:period_id AS UUID)
                  AND report_type = 'meta_ads'
                  AND status IN (
                      'queued', 'running', 'retrying', 'cancel_requested'
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"client_id": client_id, "period_id": period_id},
        ).mappings().first()
        if active:
            raise ReportDataLockedError(dict(active))
        return dict(period)

    def active_job(
        self,
        client_id: str,
        period_id: str,
        report_type: str | None = None,
    ) -> dict | None:
        normalized_type = (
            _normalize_report_type(report_type)
            if report_type is not None
            else None
        )
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_generation_jobs
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                      AND (
                          CAST(:report_type AS TEXT) IS NULL
                          OR report_type = CAST(:report_type AS TEXT)
                      )
                      AND status IN (
                          'queued',
                          'running',
                          'retrying',
                          'cancel_requested'
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "client_id": client_id,
                    "period_id": period_id,
                    "report_type": normalized_type,
                },
            ).mappings().first()
            return _row_dict(row)

    def create_job(
        self,
        client_id: str,
        period_id: str,
        *,
        dry_run: bool = False,
        requested_by: str | None = None,
        retry_of_job_id: str | None = None,
        report_options: dict | None = None,
        max_attempts: int = 3,
    ) -> dict:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        actor = str(requested_by or "").strip() or None
        normalized_options = dict(report_options or {})
        report_type = _normalize_report_type(
            normalized_options.get("report_type")
        )
        normalized_options["report_type"] = report_type

        try:
            with self.engine.begin() as conn:
                context = self._context(
                    conn,
                    client_id,
                    period_id,
                    report_type,
                )
                if report_type == "meta_ads":
                    self._lock_ads_period(conn, client_id, period_id)
                else:
                    lock_report_period(conn, client_id, period_id)
                row = conn.execute(
                    text(
                        """
                        INSERT INTO report_generation_jobs (
                            client_id,
                            report_period_id,
                            report_type,
                            retry_of_job_id,
                            client_name_snapshot,
                            period_label_snapshot,
                            dry_run,
                            requested_by,
                            max_attempts,
                            presentation_id,
                            presentation_url,
                            report_name,
                            result_metadata
                        )
                        VALUES (
                            :client_id,
                            :period_id,
                            :report_type,
                            :retry_of_job_id,
                            :client_name,
                            :period_label,
                            :dry_run,
                            :requested_by,
                            :max_attempts,
                            (
                                SELECT presentation_id
                                FROM report_generation_jobs
                                WHERE id = :retry_of_job_id
                            ),
                            (
                                SELECT presentation_url
                                FROM report_generation_jobs
                                WHERE id = :retry_of_job_id
                            ),
                            (
                                SELECT report_name
                                FROM report_generation_jobs
                                WHERE id = :retry_of_job_id
                            ),
                            COALESCE(
                                (
                                    SELECT result_metadata
                                    FROM report_generation_jobs
                                    WHERE id = :retry_of_job_id
                                ),
                                CAST(:report_options AS JSONB)
                            )
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "client_id": context["client_id"],
                        "period_id": context["report_period_id"],
                        "report_type": report_type,
                        "retry_of_job_id": retry_of_job_id,
                        "client_name": context["client_name"],
                        "period_label": context["period_label"],
                        "dry_run": bool(dry_run),
                        "requested_by": actor,
                        "max_attempts": max_attempts,
                        "report_options": _json_parameter(normalized_options),
                    },
                ).mappings().one()
                return dict(row)
        except ReportDataLockedError as exc:
            raise ActiveReportJobError(exc.job) from exc
        except IntegrityError as exc:
            active = self.active_job(client_id, period_id, report_type)
            if active:
                raise ActiveReportJobError(active) from exc
            raise

    def get_job(self, job_id: str) -> dict:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_generation_jobs
                    WHERE id = :job_id
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()
        job = _row_dict(row)
        if not job:
            raise ReportJobNotFoundError("Report generation job not found.")
        return job

    def list_for_period(
        self,
        client_id: str,
        period_id: str,
        *,
        limit: int = 20,
    ) -> list[dict]:
        safe_limit = max(1, min(int(limit), 100))
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_generation_jobs
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {
                    "client_id": client_id,
                    "period_id": period_id,
                    "limit": safe_limit,
                },
            ).mappings()
            return [dict(row) for row in rows]

    def list_for_client(
        self,
        client_id: str,
        *,
        limit: int = 100,
        report_type: str | None = None,
    ) -> list[dict]:
        safe_limit = max(1, min(int(limit), 100))
        normalized_type = (
            _normalize_report_type(report_type)
            if report_type is not None
            else None
        )
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_generation_jobs
                    WHERE client_id = :client_id
                      AND (
                          CAST(:report_type AS TEXT) IS NULL
                          OR report_type = CAST(:report_type AS TEXT)
                      )
                    ORDER BY
                        CASE
                            WHEN status IN (
                                'queued',
                                'running',
                                'retrying',
                                'cancel_requested'
                            ) THEN 0
                            ELSE 1
                        END,
                        created_at DESC
                    LIMIT :limit
                    """
                ),
                {
                    "client_id": client_id,
                    "limit": safe_limit,
                    "report_type": normalized_type,
                },
            ).mappings()
            return [dict(row) for row in rows]

    def _list_paginated(
        self,
        *,
        client_id: str | None = None,
        report_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        safe_page = max(1, int(page))
        safe_page_size = max(1, min(int(page_size), 100))
        scope_sql = ""
        parameters: dict[str, Any] = {}
        if client_id is not None:
            scope_sql = "AND client_id = :client_id"
            parameters["client_id"] = client_id
        if report_type is not None:
            scope_sql += " AND report_type = :report_type"
            parameters["report_type"] = _normalize_report_type(report_type)

        with self.engine.begin() as conn:
            count_row = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM report_generation_jobs
                    WHERE status IN ('completed', 'failed', 'cancelled')
                    {scope_sql}
                    """
                ),
                parameters,
            ).mappings().first()
            total = int((count_row or {}).get("total") or 0)
            total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
            safe_page = min(safe_page, total_pages)
            offset = (safe_page - 1) * safe_page_size

            active_rows = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM report_generation_jobs
                    WHERE status IN (
                        'queued',
                        'running',
                        'retrying',
                        'cancel_requested'
                    )
                    {scope_sql}
                    ORDER BY created_at DESC
                    """
                ),
                parameters,
            ).mappings()
            history_rows = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM report_generation_jobs
                    WHERE status IN ('completed', 'failed', 'cancelled')
                    {scope_sql}
                    ORDER BY created_at DESC
                    LIMIT :page_size
                    OFFSET :offset
                    """
                ),
                {
                    **parameters,
                    "page_size": safe_page_size,
                    "offset": offset,
                },
            ).mappings()

            jobs = [dict(row) for row in active_rows]
            jobs.extend(dict(row) for row in history_rows)

        return {
            "jobs": jobs,
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total": total,
                "total_pages": total_pages,
            },
        }

    def list_for_client_paginated(
        self,
        client_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        report_type: str | None = None,
    ) -> dict:
        return self._list_paginated(
            client_id=client_id,
            report_type=report_type,
            page=page,
            page_size=page_size,
        )

    def list_all(
        self,
        *,
        limit: int = 100,
        report_type: str | None = None,
    ) -> list[dict]:
        safe_limit = max(1, min(int(limit), 100))
        normalized_type = (
            _normalize_report_type(report_type)
            if report_type is not None
            else None
        )
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_generation_jobs
                    WHERE (
                        CAST(:report_type AS TEXT) IS NULL
                        OR report_type = CAST(:report_type AS TEXT)
                    )
                    ORDER BY
                        CASE
                            WHEN status IN (
                                'queued',
                                'running',
                                'retrying',
                                'cancel_requested'
                            ) THEN 0
                            ELSE 1
                        END,
                        created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": safe_limit, "report_type": normalized_type},
            ).mappings()
            return [dict(row) for row in rows]

    def list_all_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        report_type: str | None = None,
    ) -> dict:
        return self._list_paginated(
            page=page,
            page_size=page_size,
            report_type=report_type,
        )

    def set_cloud_task_name(self, job_id: str, task_name: str) -> dict:
        return self._transition(
            job_id,
            "queued",
            """
            UPDATE report_generation_jobs
            SET cloud_task_name = :task_name,
                updated_at = now()
            WHERE id = :job_id
              AND status = 'queued'
            RETURNING *
            """,
            {"job_id": job_id, "task_name": task_name},
        )

    def claim_job(self, job_id: str, *, lease_seconds: int = 900) -> dict:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be at least 1.")
        return self._transition(
            job_id,
            "running",
            """
            UPDATE report_generation_jobs
            SET status = 'running',
                current_stage = 'analysis',
                attempt_count = attempt_count + 1,
                started_at = COALESCE(started_at, now()),
                lease_expires_at =
                    now() + (:lease_seconds * INTERVAL '1 second'),
                error_code = NULL,
                error_message = NULL,
                updated_at = now()
            WHERE id = :job_id
              AND (
                  status IN ('queued', 'retrying')
                  OR (
                      status = 'running'
                      AND lease_expires_at <= now()
                  )
              )
              AND attempt_count < max_attempts
            RETURNING *
            """,
            {"job_id": job_id, "lease_seconds": lease_seconds},
        )

    def fail_expired_job(self, job_id: str) -> dict:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE report_generation_jobs
                    SET status = 'failed',
                        current_stage = 'failed',
                        error_code = 'MAX_ATTEMPTS_EXCEEDED',
                        error_message = (
                            'Report worker lease expired after the maximum '
                            'number of attempts.'
                        ),
                        finished_at = now(),
                        lease_expires_at = NULL,
                        updated_at = now()
                    WHERE id = :job_id
                      AND status = 'running'
                      AND lease_expires_at <= now()
                      AND attempt_count >= max_attempts
                    RETURNING *
                    """
                ),
                {"job_id": job_id},
            ).mappings().first()
        return _row_dict(row) or self.get_job(job_id)

    def update_progress(
        self,
        job_id: str,
        stage: str,
        *,
        lease_seconds: int = 900,
    ) -> dict:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be at least 1.")
        normalized_stage = str(stage or "").strip()
        if not normalized_stage:
            raise ValueError("stage is required.")

        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE report_generation_jobs
                    SET current_stage = :stage,
                        lease_expires_at =
                            now() + (:lease_seconds * INTERVAL '1 second'),
                        updated_at = now()
                    WHERE id = :job_id
                      AND status = 'running'
                    RETURNING *
                    """
                ),
                {
                    "job_id": job_id,
                    "stage": normalized_stage,
                    "lease_seconds": lease_seconds,
                },
            ).mappings().first()
        return _row_dict(row) or self.get_job(job_id)

    def record_presentation(
        self,
        job_id: str,
        *,
        presentation_id: str,
        presentation_url: str,
        report_name: str,
        lease_seconds: int = 900,
    ) -> dict:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be at least 1.")
        return self._transition(
            job_id,
            "running",
            """
            UPDATE report_generation_jobs
            SET current_stage = CASE
                    WHEN status = 'cancel_requested'
                    THEN current_stage
                    ELSE 'slides'
                END,
                presentation_id = :presentation_id,
                presentation_url = :presentation_url,
                report_name = :report_name,
                lease_expires_at = CASE
                    WHEN status = 'cancel_requested'
                    THEN lease_expires_at
                    ELSE now() + (:lease_seconds * INTERVAL '1 second')
                END,
                updated_at = now()
            WHERE id = :job_id
              AND status IN ('running', 'cancel_requested')
            RETURNING *
            """,
            {
                "job_id": job_id,
                "presentation_id": presentation_id,
                "presentation_url": presentation_url,
                "report_name": report_name,
                "lease_seconds": lease_seconds,
            },
        )

    def complete_job(
        self,
        job_id: str,
        *,
        presentation_id: str | None = None,
        presentation_url: str | None = None,
        report_name: str | None = None,
        gemini_usage: dict | None = None,
        result_metadata: dict | None = None,
        source_data_version: str | None = None,
        analysis_cache_hit: bool = False,
    ) -> dict:
        return self._transition(
            job_id,
            "completed",
            """
            UPDATE report_generation_jobs
            SET status = 'completed',
                current_stage = 'completed',
                presentation_id = :presentation_id,
                presentation_url = :presentation_url,
                report_name = :report_name,
                gemini_usage = CAST(:gemini_usage AS JSONB),
                result_metadata = CAST(:result_metadata AS JSONB),
                source_data_version = :source_data_version,
                analysis_cache_hit = :analysis_cache_hit,
                error_code = NULL,
                error_message = NULL,
                finished_at = now(),
                lease_expires_at = NULL,
                updated_at = now()
            WHERE id = :job_id
              AND status = 'running'
            RETURNING *
            """,
            {
                "job_id": job_id,
                "presentation_id": presentation_id,
                "presentation_url": presentation_url,
                "report_name": report_name,
                "gemini_usage": _json_parameter(gemini_usage),
                "result_metadata": _json_parameter(result_metadata),
                "source_data_version": source_data_version,
                "analysis_cache_hit": bool(analysis_cache_hit),
            },
        )

    def mark_retrying(
        self,
        job_id: str,
        error_message: str,
        *,
        error_code: str | None = None,
    ) -> dict:
        return self._transition(
            job_id,
            "retrying",
            """
            UPDATE report_generation_jobs
            SET status = 'retrying',
                current_stage = 'queued',
                error_code = :error_code,
                error_message = :error_message,
                lease_expires_at = NULL,
                updated_at = now()
            WHERE id = :job_id
              AND status = 'running'
              AND attempt_count < max_attempts
            RETURNING *
            """,
            {
                "job_id": job_id,
                "error_code": error_code,
                "error_message": str(error_message),
            },
        )

    def request_cancel(
        self,
        job_id: str,
        *,
        cancelled_by: str | None = None,
        reason: str | None = None,
    ) -> dict:
        actor = str(cancelled_by or "").strip() or None
        cancel_reason = str(reason or "").strip() or None
        return self._transition(
            job_id,
            "cancel_requested",
            """
            UPDATE report_generation_jobs
            SET status = CASE
                    WHEN status IN ('queued', 'retrying') THEN 'cancelled'
                    ELSE 'cancel_requested'
                END,
                current_stage = CASE
                    WHEN status IN ('queued', 'retrying') THEN 'cancelled'
                    ELSE 'cancel_requested'
                END,
                cancel_reason = :cancel_reason,
                cancelled_by = :cancelled_by,
                cancel_requested_at = now(),
                cancelled_at = CASE
                    WHEN status IN ('queued', 'retrying') THEN now()
                    ELSE cancelled_at
                END,
                finished_at = CASE
                    WHEN status IN ('queued', 'retrying') THEN now()
                    ELSE finished_at
                END,
                lease_expires_at = CASE
                    WHEN status IN ('queued', 'retrying') THEN NULL
                    ELSE lease_expires_at
                END,
                updated_at = now()
            WHERE id = :job_id
              AND status IN ('queued', 'running', 'retrying')
            RETURNING *
            """,
            {
                "job_id": job_id,
                "cancel_reason": cancel_reason,
                "cancelled_by": actor,
            },
        )

    def mark_cancelled(self, job_id: str) -> dict:
        return self._transition(
            job_id,
            "cancelled",
            """
            UPDATE report_generation_jobs
            SET status = 'cancelled',
                current_stage = 'cancelled',
                cancelled_at = COALESCE(cancelled_at, now()),
                finished_at = COALESCE(finished_at, now()),
                lease_expires_at = NULL,
                result_metadata = COALESCE(
                    result_metadata,
                    '{}'::jsonb
                ) || jsonb_build_object(
                    'cancel_latency_seconds',
                    ROUND(
                        EXTRACT(
                            EPOCH FROM (
                                now() - COALESCE(cancel_requested_at, now())
                            )
                        )::numeric,
                        3
                    )
                ),
                updated_at = now()
            WHERE id = :job_id
              AND status = 'cancel_requested'
            RETURNING *
            """,
            {"job_id": job_id},
        )

    def record_cancellation_cleanup(
        self,
        job_id: str,
        cleanup: dict,
        *,
        clear_presentation: bool = False,
    ) -> dict:
        cleanup_payload = dict(cleanup or {})
        renamed_report_name = (
            str(cleanup_payload.get("report_name") or "").strip() or None
        )
        return self._transition(
            job_id,
            "cancelled",
            """
            UPDATE report_generation_jobs
            SET presentation_id = CASE
                    WHEN :clear_presentation THEN NULL
                    ELSE presentation_id
                END,
                presentation_url = CASE
                    WHEN :clear_presentation THEN NULL
                    ELSE presentation_url
                END,
                report_name = CASE
                    WHEN :clear_presentation THEN NULL
                    ELSE COALESCE(:renamed_report_name, report_name)
                END,
                result_metadata = COALESCE(
                    result_metadata,
                    '{}'::jsonb
                ) || jsonb_build_object(
                    'cancellation_cleanup',
                    CAST(:cleanup AS JSONB)
                ),
                updated_at = now()
            WHERE id = :job_id
              AND status = 'cancelled'
            RETURNING *
            """,
            {
                "job_id": job_id,
                "cleanup": _json_parameter(cleanup_payload),
                "clear_presentation": bool(clear_presentation),
                "renamed_report_name": renamed_report_name,
            },
        )

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        *,
        error_code: str | None = None,
    ) -> dict:
        return self._transition(
            job_id,
            "failed",
            """
            UPDATE report_generation_jobs
            SET status = 'failed',
                current_stage = 'failed',
                error_code = :error_code,
                error_message = :error_message,
                finished_at = now(),
                lease_expires_at = NULL,
                updated_at = now()
            WHERE id = :job_id
              AND status IN ('queued', 'running', 'retrying')
            RETURNING *
            """,
            {
                "job_id": job_id,
                "error_code": error_code,
                "error_message": str(error_message),
            },
        )

    def _transition(
        self,
        job_id: str,
        target_status: str,
        statement: str,
        parameters: dict,
    ) -> dict:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(statement),
                parameters,
            ).mappings().first()
        job = _row_dict(row)
        if job:
            return job
        current = self.get_job(job_id)
        raise ReportJobTransitionError(current, target_status)
