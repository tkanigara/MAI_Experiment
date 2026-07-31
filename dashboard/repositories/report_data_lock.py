from __future__ import annotations

from sqlalchemy import text


ACTIVE_JOB_STATUSES = ("queued", "running", "retrying", "cancel_requested")


class ReportDataLockedError(Exception):
    code = "REPORT_PERIOD_LOCKED"

    def __init__(self, job: dict):
        self.job = dict(job)
        super().__init__(
            "Report data is locked while report generation is active."
        )


def _active_job(conn, where_sql: str, parameters: dict) -> dict | None:
    row = conn.execute(
        text(
            f"""
            SELECT
                id,
                client_id,
                report_period_id,
                client_name_snapshot,
                period_label_snapshot,
                status,
                current_stage,
                dry_run,
                presentation_url,
                queued_at,
                started_at,
                updated_at
            FROM report_generation_jobs
            WHERE {where_sql}
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
        parameters,
    ).mappings().first()
    return dict(row) if row else None


def _raise_if_active(conn, where_sql: str, parameters: dict) -> None:
    job = _active_job(conn, where_sql, parameters)
    if job:
        raise ReportDataLockedError(job)


def lock_report_period(conn, client_id: str, period_id: str) -> dict:
    period = conn.execute(
        text(
            """
            SELECT id, client_id, period_label, period_start
            FROM report_periods
            WHERE id = CAST(:period_id AS UUID)
              AND client_id = CAST(:client_id AS UUID)
            FOR UPDATE
            """
        ),
        {"client_id": client_id, "period_id": period_id},
    ).mappings().first()
    if not period:
        raise ValueError("Report month not found")
    _raise_if_active(
        conn,
        (
            "client_id = CAST(:client_id AS UUID) "
            "AND report_period_id = CAST(:period_id AS UUID)"
        ),
        {"client_id": client_id, "period_id": period_id},
    )
    return dict(period)


def lock_existing_report_period(
    conn,
    client_id: str,
    period_start,
    period_end,
) -> dict | None:
    period = conn.execute(
        text(
            """
            SELECT id, client_id, period_label, period_start
            FROM report_periods
            WHERE client_id = CAST(:client_id AS UUID)
              AND period_start = :period_start
              AND period_end = :period_end
            FOR UPDATE
            """
        ),
        {
            "client_id": client_id,
            "period_start": period_start,
            "period_end": period_end,
        },
    ).mappings().first()
    if not period:
        return None
    period = dict(period)
    _raise_if_active(
        conn,
        (
            "client_id = CAST(:client_id AS UUID) "
            "AND report_period_id = CAST(:period_id AS UUID)"
        ),
        {"client_id": client_id, "period_id": period["id"]},
    )
    return period


def lock_client_report_periods(conn, client_id: str) -> None:
    list(
        conn.execute(
            text(
                """
                SELECT id
                FROM report_periods
                WHERE client_id = CAST(:client_id AS UUID)
                ORDER BY id
                FOR UPDATE
                """
            ),
            {"client_id": client_id},
        ).mappings()
    )
    _raise_if_active(
        conn,
        "client_id = CAST(:client_id AS UUID)",
        {"client_id": client_id},
    )


def lock_client_report_year(conn, client_id: str, period_year: int) -> None:
    list(
        conn.execute(
            text(
                """
                SELECT id
                FROM report_periods
                WHERE client_id = CAST(:client_id AS UUID)
                  AND EXTRACT(YEAR FROM period_start) = :period_year
                ORDER BY id
                FOR UPDATE
                """
            ),
            {"client_id": client_id, "period_year": period_year},
        ).mappings()
    )
    _raise_if_active(
        conn,
        """
        client_id = CAST(:client_id AS UUID)
        AND report_period_id IN (
            SELECT id
            FROM report_periods
            WHERE client_id = CAST(:client_id AS UUID)
              AND EXTRACT(YEAR FROM period_start) = :period_year
        )
        """,
        {"client_id": client_id, "period_year": period_year},
    )
