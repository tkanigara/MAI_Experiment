from __future__ import annotations

import json
import os
from typing import Callable, Protocol

try:
    from dashboard.repositories.report_job_repository import (
        TERMINAL_JOB_STATUSES,
        ReportJobRepository,
        ReportJobTransitionError,
    )
except ModuleNotFoundError:
    from repositories.report_job_repository import (
        TERMINAL_JOB_STATUSES,
        ReportJobRepository,
        ReportJobTransitionError,
    )


class ReportQueueUnavailableError(RuntimeError):
    pass


class ReportTaskDispatchError(RuntimeError):
    pass


class ReportTaskAuthenticationError(RuntimeError):
    pass


class ReportGenerationCancelledError(RuntimeError):
    pass


class RetryableReportJobError(RuntimeError):
    pass


class ReportJobAlreadyRunningError(RuntimeError):
    pass


class ReportTaskDispatcher(Protocol):
    @property
    def configured(self) -> bool:
        ...

    def enqueue(self, job: dict) -> str:
        ...

    def cancel(self, task_name: str) -> bool:
        ...


class UnconfiguredReportTaskDispatcher:
    @property
    def configured(self) -> bool:
        return False

    def enqueue(self, job: dict) -> str:
        raise ReportQueueUnavailableError(
            "Report queue is not configured in this environment."
        )

    def cancel(self, task_name: str) -> bool:
        return False


class CloudTasksReportTaskDispatcher:
    def __init__(
        self,
        *,
        project: str,
        location: str,
        queue: str,
        worker_base_url: str,
        oidc_service_account: str,
        oidc_audience: str | None = None,
        dispatch_deadline_seconds: int = 900,
        client=None,
    ):
        self.project = str(project or "").strip()
        self.location = str(location or "").strip()
        self.queue = str(queue or "").strip()
        self.worker_base_url = str(worker_base_url or "").strip().rstrip("/")
        self.oidc_service_account = str(oidc_service_account or "").strip()
        self.oidc_audience = (
            str(oidc_audience or "").strip() or self.worker_base_url
        )
        self.dispatch_deadline_seconds = max(
            1,
            min(int(dispatch_deadline_seconds), 1800),
        )
        if client is None:
            from google.cloud import tasks_v2

            client = tasks_v2.CloudTasksClient()
        self.client = client

    @property
    def configured(self) -> bool:
        return all(
            (
                self.project,
                self.location,
                self.queue,
                self.worker_base_url,
                self.oidc_service_account,
                self.oidc_audience,
            )
        )

    def _require_configured(self) -> None:
        if not self.configured:
            raise ReportQueueUnavailableError(
                "Cloud Tasks report queue configuration is incomplete."
            )

    def enqueue(self, job: dict) -> str:
        self._require_configured()
        job_id = str(job["id"])
        parent = (
            f"projects/{self.project}/locations/{self.location}/"
            f"queues/{self.queue}"
        )
        task_id = f"report-job-{job_id.replace('-', '')}"
        task_name = f"{parent}/tasks/{task_id}"
        response = self.client.create_task(
            request={
                "parent": parent,
                "task": {
                    "name": task_name,
                    "dispatch_deadline": {
                        "seconds": self.dispatch_deadline_seconds,
                    },
                    "http_request": {
                        "http_method": "POST",
                        "url": (
                            f"{self.worker_base_url}/internal/"
                            f"report-jobs/{job_id}/execute"
                        ),
                        "headers": {"Content-Type": "application/json"},
                        "body": json.dumps(
                            {"job_id": job_id},
                            separators=(",", ":"),
                        ).encode("utf-8"),
                        "oidc_token": {
                            "service_account_email": self.oidc_service_account,
                            "audience": self.oidc_audience,
                        },
                    },
                },
            }
        )
        return str(getattr(response, "name", None) or task_name)

    def cancel(self, task_name: str) -> bool:
        self._require_configured()
        try:
            self.client.delete_task(request={"name": task_name})
        except Exception as exc:
            if type(exc).__name__ == "NotFound":
                return False
            raise
        return True


def build_report_task_dispatcher() -> ReportTaskDispatcher:
    backend = os.getenv("REPORT_QUEUE_BACKEND", "").strip().lower()
    if backend not in {"cloud_tasks", "cloud-tasks"}:
        return UnconfiguredReportTaskDispatcher()
    return CloudTasksReportTaskDispatcher(
        project=os.getenv("CLOUD_TASKS_PROJECT", ""),
        location=os.getenv("CLOUD_TASKS_LOCATION", ""),
        queue=os.getenv("CLOUD_TASKS_QUEUE", ""),
        worker_base_url=os.getenv("REPORT_WORKER_BASE_URL", ""),
        oidc_service_account=os.getenv(
            "REPORT_TASK_CALLER_SERVICE_ACCOUNT",
            "",
        ),
        oidc_audience=os.getenv("REPORT_TASK_OIDC_AUDIENCE"),
        dispatch_deadline_seconds=int(
            os.getenv("REPORT_TASK_DISPATCH_DEADLINE_SECONDS", "900")
        ),
    )


def verify_cloud_tasks_oidc(
    authorization: str | None,
    *,
    audience: str | None = None,
    service_account: str | None = None,
    verifier: Callable[[str, str], dict] | None = None,
) -> dict:
    expected_audience = str(
        audience
        or os.getenv("REPORT_TASK_OIDC_AUDIENCE")
        or os.getenv("REPORT_WORKER_BASE_URL")
        or ""
    ).strip()
    expected_service_account = str(
        service_account
        or os.getenv("REPORT_TASK_CALLER_SERVICE_ACCOUNT")
        or ""
    ).strip().lower()
    if not expected_audience or not expected_service_account:
        raise ReportTaskAuthenticationError(
            "Cloud Tasks OIDC verification is not configured."
        )

    scheme, _, token = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ReportTaskAuthenticationError(
            "A Cloud Tasks bearer token is required."
        )

    if verifier is None:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token

        def verifier(raw_token: str, target_audience: str) -> dict:
            return id_token.verify_oauth2_token(
                raw_token,
                GoogleRequest(),
                target_audience,
            )

    try:
        claims = dict(verifier(token.strip(), expected_audience))
    except Exception as exc:
        raise ReportTaskAuthenticationError(
            "Cloud Tasks bearer token is invalid."
        ) from exc

    token_email = str(claims.get("email") or "").strip().lower()
    email_verified = claims.get("email_verified")
    if token_email != expected_service_account or email_verified not in {
        True,
        "true",
    }:
        raise ReportTaskAuthenticationError(
            "Cloud Tasks token identity is not allowed."
        )
    return claims


class ReportJobService:
    def __init__(
        self,
        repository: ReportJobRepository,
        dispatcher: ReportTaskDispatcher,
    ):
        self.repository = repository
        self.dispatcher = dispatcher

    def create_job(
        self,
        client_id: str,
        period_id: str,
        *,
        dry_run: bool = False,
        requested_by: str | None = None,
        retry_of_job_id: str | None = None,
    ) -> dict:
        if not self.dispatcher.configured:
            raise ReportQueueUnavailableError(
                "Report queue is not configured in this environment."
            )

        job = self.repository.create_job(
            client_id,
            period_id,
            dry_run=dry_run,
            requested_by=requested_by,
            retry_of_job_id=retry_of_job_id,
        )
        try:
            task_name = self.dispatcher.enqueue(job)
        except Exception as exc:
            self.repository.fail_job(
                str(job["id"]),
                "Failed to enqueue report generation.",
                error_code="QUEUE_DISPATCH_FAILED",
            )
            raise ReportTaskDispatchError(
                "Failed to enqueue report generation."
            ) from exc
        return self.repository.set_cloud_task_name(str(job["id"]), task_name)

    def get_job(self, job_id: str) -> dict:
        return self.repository.get_job(job_id)

    def history(
        self,
        client_id: str,
        period_id: str,
        *,
        limit: int = 20,
    ) -> list[dict]:
        return self.repository.list_for_period(
            client_id,
            period_id,
            limit=limit,
        )

    def client_history(
        self,
        client_id: str,
        *,
        limit: int = 100,
    ) -> list[dict]:
        return self.repository.list_for_client(
            client_id,
            limit=limit,
        )

    def all_history(self, *, limit: int = 100) -> list[dict]:
        return self.repository.list_all(limit=limit)

    def retry_job(
        self,
        job_id: str,
        *,
        requested_by: str | None = None,
    ) -> dict:
        previous = self.repository.get_job(job_id)
        if previous.get("status") not in {"failed", "cancelled"}:
            raise ReportJobTransitionError(previous, "queued")
        return self.create_job(
            str(previous["client_id"]),
            str(previous["report_period_id"]),
            dry_run=bool(previous.get("dry_run")),
            requested_by=requested_by,
            retry_of_job_id=str(previous["id"]),
        )

    def cancel_job(
        self,
        job_id: str,
        *,
        cancelled_by: str | None = None,
        reason: str | None = None,
    ) -> dict:
        job = self.repository.get_job(job_id)
        if job.get("status") in TERMINAL_JOB_STATUSES:
            raise ReportJobTransitionError(job, "cancel_requested")

        task_name = str(job.get("cloud_task_name") or "").strip()
        if task_name:
            try:
                self.dispatcher.cancel(task_name)
            except Exception as exc:
                # Database state is authoritative. The task handler will see
                # cancelled/cancel_requested and avoid starting new work.
                print(
                    "[report_queue] task deletion failed "
                    f"job_id={job_id} error={type(exc).__name__}",
                    flush=True,
                )

        return self.repository.request_cancel(
            job_id,
            cancelled_by=cancelled_by,
            reason=reason,
        )


class ReportJobWorker:
    def __init__(
        self,
        repository: ReportJobRepository,
        generator: Callable[..., dict],
        *,
        lease_seconds: int = 900,
    ):
        self.repository = repository
        self.generator = generator
        self.lease_seconds = max(1, int(lease_seconds))

    def _finish_cancellation(self, job: dict) -> dict:
        if job.get("status") == "cancel_requested":
            return self.repository.mark_cancelled(str(job["id"]))
        return job

    def _is_cancel_requested(self, job_id: str) -> bool:
        return self.repository.get_job(job_id).get("status") in {
            "cancel_requested",
            "cancelled",
        }

    def execute(self, job_id: str) -> dict:
        job = self.repository.get_job(job_id)
        if job.get("status") in TERMINAL_JOB_STATUSES:
            return job
        if job.get("status") == "cancel_requested":
            return self._finish_cancellation(job)

        try:
            job = self.repository.claim_job(
                job_id,
                lease_seconds=self.lease_seconds,
            )
        except ReportJobTransitionError:
            current = self.repository.get_job(job_id)
            if current.get("status") in TERMINAL_JOB_STATUSES:
                return current
            if current.get("status") == "cancel_requested":
                return self._finish_cancellation(current)
            if current.get("status") == "running":
                current = self.repository.fail_expired_job(job_id)
                if current.get("status") == "failed":
                    return current
                # Cloud Tasks delivery is at-least-once. Keep the duplicate
                # task retryable until the active worker reaches a terminal
                # state; never start a second run during an active lease.
                raise ReportJobAlreadyRunningError(
                    "Report generation is already running."
                )
            raise

        def should_cancel() -> bool:
            return self._is_cancel_requested(job_id)

        def on_stage(stage: str) -> None:
            current = self.repository.update_progress(
                job_id,
                stage,
                lease_seconds=self.lease_seconds,
            )
            if current.get("status") in {"cancel_requested", "cancelled"}:
                raise ReportGenerationCancelledError(
                    "Report generation was cancelled."
                )

        def on_presentation_created(presentation: dict) -> None:
            self.repository.record_presentation(
                job_id,
                presentation_id=str(presentation["presentation_id"]),
                presentation_url=str(presentation["presentation_url"]),
                report_name=str(presentation["report_name"]),
                lease_seconds=self.lease_seconds,
            )

        try:
            result = self.generator(
                str(job["client_id"]),
                str(job["report_period_id"]),
                dry_run=bool(job.get("dry_run")),
                should_cancel=should_cancel,
                on_stage=on_stage,
                on_presentation_created=on_presentation_created,
                existing_presentation_id=job.get("presentation_id"),
                existing_report_name=job.get("report_name"),
            )
            if should_cancel():
                raise ReportGenerationCancelledError(
                    "Report generation was cancelled."
                )

            result_metadata = {
                key: result.get(key)
                for key in (
                    "status",
                    "fast_mode",
                    "filter_to_template",
                    "total_duration_seconds",
                )
                if result.get(key) is not None
            }
            return self.repository.complete_job(
                job_id,
                presentation_id=result.get("presentation_id"),
                presentation_url=result.get("presentation_url"),
                report_name=result.get("report_name"),
                gemini_usage=result.get("gemini_usage"),
                result_metadata=result_metadata,
                source_data_version=result.get("source_data_version"),
                analysis_cache_hit=bool(result.get("analysis_cache_hit")),
            )
        except ReportGenerationCancelledError:
            return self._finish_cancellation(
                self.repository.get_job(job_id)
            )
        except Exception as exc:
            current = self.repository.get_job(job_id)
            if current.get("status") in {"cancel_requested", "cancelled"}:
                return self._finish_cancellation(current)
            if current.get("status") != "running":
                raise

            error_message = str(exc) or type(exc).__name__
            if int(current.get("attempt_count") or 0) < int(
                current.get("max_attempts") or 1
            ):
                self.repository.mark_retrying(
                    job_id,
                    error_message,
                    error_code=type(exc).__name__,
                )
                raise RetryableReportJobError(error_message) from exc

            return self.repository.fail_job(
                job_id,
                error_message,
                error_code=type(exc).__name__,
            )
