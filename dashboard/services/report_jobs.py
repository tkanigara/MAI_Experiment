from __future__ import annotations

import importlib
import json
import multiprocessing
import os
import queue as queue_module
import threading
import time
import traceback
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


class ReportGeneratorProcessError(RuntimeError):
    def __init__(self, error_code: str, message: str, child_traceback: str = ""):
        self.error_code = str(error_code or "ReportGeneratorProcessError")
        self.child_traceback = str(child_traceback or "")
        super().__init__(message or self.error_code)


def _callable_reference(callback: Callable) -> tuple[str, str] | None:
    module_name = str(getattr(callback, "__module__", "") or "").strip()
    qualname = str(getattr(callback, "__qualname__", "") or "").strip()
    if not module_name or not qualname or "<locals>" in qualname:
        return None
    return module_name, qualname


def _resolve_callable(module_name: str, qualname: str) -> Callable:
    value = importlib.import_module(module_name)
    for part in qualname.split("."):
        value = getattr(value, part)
    if not callable(value):
        raise TypeError(f"{module_name}.{qualname} is not callable.")
    return value


def _report_generator_process_entry(
    module_name: str,
    qualname: str,
    client_id: str,
    period_id: str,
    options: dict,
    cancel_event,
    message_connection,
) -> None:
    send_lock = threading.Lock()

    def send(kind: str, payload=None) -> None:
        with send_lock:
            message_connection.send((kind, payload))

    try:
        generator = _resolve_callable(module_name, qualname)
        result = generator(
            client_id,
            period_id,
            dry_run=bool(options.get("dry_run")),
            should_cancel=cancel_event.is_set,
            on_stage=lambda stage: send("stage", str(stage)),
            on_presentation_created=lambda presentation: send(
                "presentation",
                dict(presentation),
            ),
            existing_presentation_id=options.get("existing_presentation_id"),
            existing_report_name=options.get("existing_report_name"),
            report_type=options.get("report_type", "social_media"),
            report_model=options.get("report_model", "jba"),
            platform_scope=options.get("platform_scope"),
            objective=options.get("objective"),
        )
        send("result", result)
    except ReportGenerationCancelledError as exc:
        send("cancelled", str(exc))
    except BaseException as exc:
        send(
            "error",
            {
                "error_code": type(exc).__name__,
                "message": str(exc) or type(exc).__name__,
                "traceback": traceback.format_exc(limit=30),
            },
        )
    finally:
        message_connection.close()


class ReportTaskDispatcher(Protocol):
    @property
    def configured(self) -> bool:
        ...

    def enqueue(self, job: dict) -> str:
        ...

    def activate(self, task_name: str) -> None:
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

    def activate(self, task_name: str) -> None:
        return None

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

    def activate(self, task_name: str) -> None:
        # Cloud Tasks is active as soon as create_task succeeds.
        return None

    def cancel(self, task_name: str) -> bool:
        self._require_configured()
        try:
            self.client.delete_task(request={"name": task_name})
        except Exception as exc:
            if type(exc).__name__ == "NotFound":
                return False
            raise
        return True


class QStashReportTaskDispatcher:
    """FIFO report dispatcher backed by an Upstash QStash queue."""

    def __init__(
        self,
        *,
        token: str,
        queue: str,
        worker_base_url: str,
        retries: int = 2,
        timeout: str | int = "14m",
        base_url: str | None = None,
        client=None,
    ):
        self.token = str(token or "").strip()
        self.queue = str(queue or "").strip()
        self.worker_base_url = str(worker_base_url or "").strip().rstrip("/")
        self.retries = max(0, int(retries))
        self.timeout = timeout
        self.base_url = str(base_url or "").strip().rstrip("/") or None
        self.client = client

    @property
    def configured(self) -> bool:
        return all((self.token, self.queue, self.worker_base_url))

    def _require_configured(self) -> None:
        if not self.configured:
            raise ReportQueueUnavailableError(
                "QStash report queue configuration is incomplete."
            )

    def _client(self):
        self._require_configured()
        if self.client is None:
            from qstash import QStash

            self.client = QStash(self.token, base_url=self.base_url)
        return self.client

    def enqueue(self, job: dict) -> str:
        job_id = str(job["id"])
        response = self._client().message.enqueue_json(
            queue=self.queue,
            url=(
                f"{self.worker_base_url}/internal/"
                f"report-jobs/{job_id}/execute"
            ),
            body={"job_id": job_id},
            retries=self.retries,
            timeout=self.timeout,
            label="report-generation",
        )
        message_id = str(getattr(response, "message_id", "") or "").strip()
        if not message_id:
            raise ReportTaskDispatchError("QStash did not return a message ID.")
        return message_id

    def activate(self, task_name: str) -> None:
        return None

    def cancel(self, task_name: str) -> bool:
        message_id = str(task_name or "").strip()
        if not message_id:
            return False
        self._client().message.cancel(message_id)
        return True


class LocalReportTaskDispatcher:
    """Single-process queue for local development only."""

    def __init__(
        self,
        execute_job: Callable[[str], dict],
        *,
        retry_delay_seconds: float = 1.0,
    ):
        self.execute_job = execute_job
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self._tasks: queue_module.Queue[tuple[str, str]] = queue_module.Queue()
        self._pending: dict[str, str] = {}
        self._queued: set[str] = set()
        self._running: set[str] = set()
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name="local-report-worker",
            daemon=True,
        )
        self._thread.start()

    @property
    def configured(self) -> bool:
        return True

    def enqueue(self, job: dict) -> str:
        job_id = str(job["id"])
        task_name = f"local/report-jobs/tasks/{job_id}"
        with self._lock:
            self._pending[task_name] = job_id
        return task_name

    def activate(self, task_name: str) -> None:
        with self._lock:
            job_id = self._pending.pop(task_name, None)
            if not job_id or task_name in self._cancelled:
                self._cancelled.discard(task_name)
                return
            self._queued.add(task_name)
        self._tasks.put((task_name, job_id))

    def cancel(self, task_name: str) -> bool:
        with self._lock:
            if task_name in self._pending:
                self._pending.pop(task_name, None)
                self._cancelled.add(task_name)
                return True
            if task_name in self._queued:
                self._cancelled.add(task_name)
                return True
            # Running jobs use the database cancel_requested flag and stop at
            # the next cooperative cancellation checkpoint.
            return False

    def _run(self) -> None:
        while True:
            task_name, job_id = self._tasks.get()
            try:
                with self._lock:
                    self._queued.discard(task_name)
                    if task_name in self._cancelled:
                        self._cancelled.discard(task_name)
                        continue
                    self._running.add(task_name)

                while True:
                    try:
                        self.execute_job(job_id)
                        break
                    except RetryableReportJobError:
                        if self.retry_delay_seconds:
                            time.sleep(self.retry_delay_seconds)
                    except Exception as exc:
                        print(
                            "[local_report_queue] worker failed "
                            f"job_id={job_id} error={type(exc).__name__}: {exc}",
                            flush=True,
                        )
                        break
            finally:
                with self._lock:
                    self._running.discard(task_name)
                    self._cancelled.discard(task_name)
                self._tasks.task_done()


def build_report_task_dispatcher(
    execute_job: Callable[[str], dict] | None = None,
) -> ReportTaskDispatcher:
    backend = os.getenv("REPORT_QUEUE_BACKEND", "").strip().lower()
    if backend in {"local", "in_process", "in-process"}:
        if execute_job is None:
            raise ReportQueueUnavailableError(
                "Local report queue requires a report worker."
            )
        return LocalReportTaskDispatcher(
            execute_job,
            retry_delay_seconds=float(
                os.getenv("REPORT_LOCAL_RETRY_DELAY_SECONDS", "1")
            ),
        )
    if backend in {"qstash", "upstash", "upstash_qstash"}:
        return QStashReportTaskDispatcher(
            token=os.getenv("QSTASH_TOKEN", ""),
            queue=os.getenv("QSTASH_QUEUE", "mai-report-generation"),
            worker_base_url=os.getenv("REPORT_WORKER_BASE_URL", ""),
            retries=int(os.getenv("QSTASH_RETRIES", "2")),
            timeout=os.getenv("QSTASH_TIMEOUT", "14m"),
            base_url=os.getenv("QSTASH_URL"),
        )
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


def verify_qstash_signature(
    signature: str | None,
    *,
    body: bytes | str,
    url: str,
    current_signing_key: str | None = None,
    next_signing_key: str | None = None,
    receiver=None,
) -> bool:
    expected_url = str(url or "").strip()
    current_key = str(
        current_signing_key or os.getenv("QSTASH_CURRENT_SIGNING_KEY") or ""
    ).strip()
    next_key = str(
        next_signing_key or os.getenv("QSTASH_NEXT_SIGNING_KEY") or ""
    ).strip()
    raw_signature = str(signature or "").strip()

    if not expected_url or not current_key or not next_key:
        raise ReportTaskAuthenticationError(
            "QStash signature verification is not configured."
        )
    if not raw_signature:
        raise ReportTaskAuthenticationError(
            "An Upstash-Signature header is required."
        )

    if receiver is None:
        from qstash import Receiver

        receiver = Receiver(
            current_signing_key=current_key,
            next_signing_key=next_key,
        )

    raw_body = body.decode("utf-8") if isinstance(body, bytes) else str(body)
    try:
        verified = receiver.verify(
            body=raw_body,
            signature=raw_signature,
            url=expected_url,
        )
    except Exception as exc:
        raise ReportTaskAuthenticationError(
            "QStash request signature is invalid."
        ) from exc
    if verified is False:
        raise ReportTaskAuthenticationError(
            "QStash request signature is invalid."
        )
    return True


def verify_report_task_request(
    *,
    authorization: str | None,
    qstash_signature: str | None,
    body: bytes | str,
    url: str,
    backend: str | None = None,
):
    selected_backend = str(
        backend if backend is not None else os.getenv("REPORT_QUEUE_BACKEND", "")
    ).strip().lower()
    if selected_backend in {"qstash", "upstash", "upstash_qstash"}:
        return verify_qstash_signature(
            qstash_signature,
            body=body,
            url=url,
        )
    if selected_backend in {"cloud_tasks", "cloud-tasks"}:
        return verify_cloud_tasks_oidc(authorization)
    raise ReportTaskAuthenticationError(
        "Remote report worker authentication is not configured."
    )


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
        report_type: str = "social_media",
        report_model: str = "jba",
        platform_scope: str | None = None,
        objective: str | None = None,
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
            report_options={
                "report_type": str(report_type or "social_media"),
                "report_model": str(report_model or "jba"),
                "platform_scope": platform_scope,
                "objective": objective,
            },
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
        try:
            queued_job = self.repository.set_cloud_task_name(
                str(job["id"]),
                task_name,
            )
        except Exception:
            self.dispatcher.cancel(task_name)
            raise
        try:
            self.dispatcher.activate(task_name)
        except Exception as exc:
            self.repository.fail_job(
                str(job["id"]),
                "Failed to start report generation.",
                error_code="QUEUE_ACTIVATION_FAILED",
            )
            self.dispatcher.cancel(task_name)
            raise ReportTaskDispatchError(
                "Failed to start report generation."
            ) from exc
        return queued_job

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
        report_type: str | None = None,
    ) -> list[dict]:
        return self.repository.list_for_client(
            client_id,
            limit=limit,
            report_type=report_type,
        )

    def client_history_page(
        self,
        client_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        report_type: str | None = None,
    ) -> dict:
        return self.repository.list_for_client_paginated(
            client_id,
            page=page,
            page_size=page_size,
            report_type=report_type,
        )

    def all_history(
        self,
        *,
        limit: int = 100,
        report_type: str | None = None,
    ) -> list[dict]:
        return self.repository.list_all(
            limit=limit,
            report_type=report_type,
        )

    def all_history_page(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        report_type: str | None = None,
    ) -> dict:
        return self.repository.list_all_paginated(
            page=page,
            page_size=page_size,
            report_type=report_type,
        )

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
            report_type=(previous.get("result_metadata") or {}).get("report_type", "social_media"),
            report_model=(previous.get("result_metadata") or {}).get("report_model", "jba"),
            platform_scope=(previous.get("result_metadata") or {}).get("platform_scope"),
            objective=(previous.get("result_metadata") or {}).get("objective"),
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

        cancelled_job = self.repository.request_cancel(
            job_id,
            cancelled_by=cancelled_by,
            reason=reason,
        )
        task_name = str(job.get("cloud_task_name") or "").strip()
        if task_name:
            def delete_dispatched_task() -> None:
                try:
                    self.dispatcher.cancel(task_name)
                except Exception as exc:
                    # Database state is authoritative. The task handler will
                    # observe cancelled/cancel_requested even if task deletion
                    # is slow or unavailable.
                    print(
                        "[report_queue] task deletion failed "
                        f"job_id={job_id} error={type(exc).__name__}",
                        flush=True,
                    )

            threading.Thread(
                target=delete_dispatched_task,
                name=f"cancel-report-task-{job_id}",
                daemon=True,
            ).start()

        return cancelled_job


class ReportJobWorker:
    def __init__(
        self,
        repository: ReportJobRepository,
        generator: Callable[..., dict],
        *,
        lease_seconds: int = 900,
        hard_cancel: bool | None = None,
        cancel_poll_seconds: float | None = None,
        cancel_grace_seconds: float | None = None,
        process_start_method: str | None = None,
        presentation_cleanup: Callable[[str, str | None], dict] | None = None,
    ):
        self.repository = repository
        self.generator = generator
        self.lease_seconds = max(1, int(lease_seconds))
        self.generator_reference = _callable_reference(generator)
        configured_hard_cancel = str(
            os.getenv("REPORT_JOB_HARD_CANCEL", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.hard_cancel = (
            configured_hard_cancel if hard_cancel is None else bool(hard_cancel)
        ) and self.generator_reference is not None
        self.cancel_poll_seconds = max(
            0.1,
            float(
                cancel_poll_seconds
                if cancel_poll_seconds is not None
                else os.getenv("REPORT_CANCEL_POLL_SECONDS", "1")
            ),
        )
        self.cancel_grace_seconds = max(
            0.0,
            float(
                cancel_grace_seconds
                if cancel_grace_seconds is not None
                else os.getenv("REPORT_CANCEL_GRACE_SECONDS", "2")
            ),
        )
        self.process_start_method = str(
            process_start_method
            or os.getenv("REPORT_JOB_PROCESS_START_METHOD", "spawn")
        ).strip()
        self.presentation_cleanup = presentation_cleanup

    def _finish_cancellation(self, job: dict) -> dict:
        if job.get("status") == "cancel_requested":
            job = self.repository.mark_cancelled(str(job["id"]))
        presentation_id = str(job.get("presentation_id") or "").strip()
        if not presentation_id:
            return job

        cleanup = self._cleanup_presentation(
            presentation_id,
            job.get("report_name"),
        )
        if hasattr(self.repository, "record_cancellation_cleanup"):
            return self.repository.record_cancellation_cleanup(
                str(job["id"]),
                cleanup,
                clear_presentation=bool(
                    cleanup.get("success")
                    and cleanup.get("action") == "trashed"
                ),
            )
        return job

    def _cleanup_presentation(
        self,
        presentation_id: str,
        report_name: str | None,
    ) -> dict:
        try:
            cleanup = self.presentation_cleanup
            if cleanup is None:
                try:
                    from dashboard.services.slides_report import (
                        cleanup_cancelled_presentation,
                    )
                except ModuleNotFoundError:
                    from services.slides_report import (
                        cleanup_cancelled_presentation,
                    )
                cleanup = cleanup_cancelled_presentation
            return dict(cleanup(presentation_id, report_name) or {})
        except Exception as exc:
            print(
                "[report_queue] cancelled presentation cleanup failed "
                f"presentation_id={presentation_id} "
                f"error={type(exc).__name__}",
                flush=True,
            )
            return {
                "success": False,
                "action": "cleanup_failed",
                "error_code": type(exc).__name__,
                "error_message": str(exc) or type(exc).__name__,
            }

    def _is_cancel_requested(self, job_id: str) -> bool:
        return self.repository.get_job(job_id).get("status") in {
            "cancel_requested",
            "cancelled",
        }

    def _run_generator_direct(
        self,
        job: dict,
        *,
        should_cancel: Callable[[], bool],
        on_stage: Callable[[str], None],
        on_presentation_created: Callable[[dict], None],
    ) -> dict:
        options = job.get("result_metadata") or {}
        return self.generator(
            str(job["client_id"]),
            str(job["report_period_id"]),
            dry_run=bool(job.get("dry_run")),
            should_cancel=should_cancel,
            on_stage=on_stage,
            on_presentation_created=on_presentation_created,
            existing_presentation_id=job.get("presentation_id"),
            existing_report_name=job.get("report_name"),
            report_type=options.get("report_type", "social_media"),
            report_model=options.get("report_model", "jba"),
            platform_scope=options.get("platform_scope"),
            objective=options.get("objective"),
        )

    def _run_generator_in_process(
        self,
        job: dict,
        *,
        should_cancel: Callable[[], bool],
        on_stage: Callable[[str], None],
        on_presentation_created: Callable[[dict], None],
    ) -> dict:
        if self.generator_reference is None:
            return self._run_generator_direct(
                job,
                should_cancel=should_cancel,
                on_stage=on_stage,
                on_presentation_created=on_presentation_created,
            )

        context = multiprocessing.get_context(self.process_start_method)
        cancel_event = context.Event()
        parent_connection, child_connection = context.Pipe(duplex=False)
        module_name, qualname = self.generator_reference
        process = context.Process(
            target=_report_generator_process_entry,
            args=(
                module_name,
                qualname,
                str(job["client_id"]),
                str(job["report_period_id"]),
                {
                    "dry_run": bool(job.get("dry_run")),
                    "existing_presentation_id": job.get("presentation_id"),
                    "existing_report_name": job.get("report_name"),
                    **(job.get("result_metadata") or {}),
                },
                cancel_event,
                child_connection,
            ),
            name=f"report-generator-{job['id']}",
        )
        try:
            process.start()
        except Exception as exc:
            parent_connection.close()
            child_connection.close()
            raise ReportGeneratorProcessError(
                "REPORT_GENERATOR_START_FAILED",
                str(exc) or "Failed to start report generator process.",
            ) from exc
        child_connection.close()
        cancel_started_at = None
        try:
            while True:
                if parent_connection.poll(self.cancel_poll_seconds):
                    try:
                        kind, payload = parent_connection.recv()
                    except EOFError:
                        if process.is_alive():
                            continue
                        raise ReportGeneratorProcessError(
                            "REPORT_GENERATOR_PIPE_CLOSED",
                            (
                                "Report generator closed its result channel "
                                f"(exit code {process.exitcode})."
                            ),
                        )
                    if kind == "stage":
                        on_stage(str(payload))
                    elif kind == "presentation":
                        on_presentation_created(dict(payload))
                    elif kind == "result":
                        process.join(timeout=2)
                        return dict(payload)
                    elif kind == "cancelled":
                        raise ReportGenerationCancelledError(
                            str(payload or "Report generation was cancelled.")
                        )
                    elif kind == "error":
                        error = dict(payload or {})
                        raise ReportGeneratorProcessError(
                            error.get("error_code"),
                            error.get("message"),
                            error.get("traceback"),
                        )

                if should_cancel():
                    if cancel_started_at is None:
                        cancel_started_at = time.monotonic()
                        cancel_event.set()
                        print(
                            "[report_queue] cancellation detected "
                            f"job_id={job['id']} grace_seconds="
                            f"{self.cancel_grace_seconds:.1f}",
                            flush=True,
                        )
                    if (
                        not process.is_alive()
                        or time.monotonic() - cancel_started_at
                        >= self.cancel_grace_seconds
                    ):
                        raise ReportGenerationCancelledError(
                            "Report generation was cancelled."
                        )

                if not process.is_alive():
                    if parent_connection.poll():
                        continue
                    raise ReportGeneratorProcessError(
                        "REPORT_GENERATOR_EXITED",
                        (
                            "Report generator exited without returning a "
                            f"result (exit code {process.exitcode})."
                        ),
                    )
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(timeout=1)
            parent_connection.close()

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
            if self.hard_cancel:
                result = self._run_generator_in_process(
                    job,
                    should_cancel=should_cancel,
                    on_stage=on_stage,
                    on_presentation_created=on_presentation_created,
                )
            else:
                result = self._run_generator_direct(
                    job,
                    should_cancel=should_cancel,
                    on_stage=on_stage,
                    on_presentation_created=on_presentation_created,
                )
            if should_cancel():
                raise ReportGenerationCancelledError(
                    "Report generation was cancelled."
                )

            result_metadata = {
                key: (job.get("result_metadata") or {}).get(key)
                for key in ("report_type", "report_model", "platform_scope", "objective")
                if (job.get("result_metadata") or {}).get(key) is not None
            }
            result_metadata.update({
                key: result.get(key)
                for key in (
                    "status",
                    "fast_mode",
                    "filter_to_template",
                    "total_duration_seconds",
                )
                if result.get(key) is not None
            })
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
            error_code = getattr(exc, "error_code", type(exc).__name__)
            child_traceback = getattr(exc, "child_traceback", "")
            if child_traceback:
                print(
                    "[report_queue] generator child traceback\n"
                    f"{child_traceback}",
                    flush=True,
                )
            if int(current.get("attempt_count") or 0) < int(
                current.get("max_attempts") or 1
            ):
                self.repository.mark_retrying(
                    job_id,
                    error_message,
                    error_code=error_code,
                )
                raise RetryableReportJobError(error_message) from exc

            return self.repository.fail_job(
                job_id,
                error_message,
                error_code=error_code,
            )
