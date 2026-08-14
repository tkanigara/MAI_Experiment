from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from report_generator_fixture import (
    blocking_generator,
    presentation_then_block_generator,
)
from dashboard.services.report_jobs import (
    CloudTasksReportTaskDispatcher,
    QStashReportTaskDispatcher,
    ReportGenerationCancelledError,
    ReportJobAlreadyRunningError,
    ReportJobWorker,
    ReportTaskAuthenticationError,
    RetryableReportJobError,
    verify_cloud_tasks_oidc,
    verify_qstash_signature,
)


class FakeTasksClient:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create_task(self, request):
        self.created.append(request)
        return SimpleNamespace(name=request["task"]["name"])

    def delete_task(self, request):
        self.deleted.append(request)


class FakeQStashMessageApi:
    def __init__(self):
        self.enqueued = []
        self.cancelled = []

    def enqueue_json(self, **request):
        self.enqueued.append(request)
        return SimpleNamespace(message_id="msg_report_job_1")

    def cancel(self, message_id):
        self.cancelled.append(message_id)


class FakeQStashClient:
    def __init__(self):
        self.message = FakeQStashMessageApi()


class FakeQStashReceiver:
    def __init__(self, *, valid=True):
        self.valid = valid
        self.requests = []

    def verify(self, **request):
        self.requests.append(request)
        if not self.valid:
            raise ValueError("invalid signature")
        return None


class FakeJobRepository:
    def __init__(self, *, status="queued", presentation_id=None):
        self.job = {
            "id": "job-1",
            "client_id": "client-1",
            "report_period_id": "period-1",
            "status": status,
            "current_stage": "queued",
            "dry_run": False,
            "attempt_count": 0,
            "max_attempts": 3,
            "presentation_id": presentation_id,
            "presentation_url": None,
            "report_name": "Existing report" if presentation_id else None,
        }
        self.recorded_presentations = []

    def get_job(self, _job_id):
        return dict(self.job)

    def claim_job(self, _job_id, *, lease_seconds):
        self.job["status"] = "running"
        self.job["current_stage"] = "analysis"
        self.job["attempt_count"] += 1
        return dict(self.job)

    def update_progress(self, _job_id, stage, *, lease_seconds):
        self.job["current_stage"] = stage
        return dict(self.job)

    def record_presentation(self, _job_id, **presentation):
        self.recorded_presentations.append(presentation)
        self.job.update(presentation)
        self.job["current_stage"] = "slides"
        return dict(self.job)

    def complete_job(self, _job_id, **result):
        self.job.update(result)
        self.job["status"] = "completed"
        self.job["current_stage"] = "completed"
        return dict(self.job)

    def mark_cancelled(self, _job_id):
        self.job["status"] = "cancelled"
        self.job["current_stage"] = "cancelled"
        return dict(self.job)

    def record_cancellation_cleanup(
        self,
        _job_id,
        cleanup,
        *,
        clear_presentation,
    ):
        self.job["result_metadata"] = {
            "cancellation_cleanup": dict(cleanup)
        }
        if clear_presentation:
            self.job["presentation_id"] = None
            self.job["presentation_url"] = None
            self.job["report_name"] = None
        return dict(self.job)

    def mark_retrying(self, _job_id, error_message, *, error_code=None):
        self.job["status"] = "retrying"
        self.job["error_message"] = error_message
        self.job["error_code"] = error_code
        return dict(self.job)

    def fail_job(self, _job_id, error_message, *, error_code=None):
        self.job["status"] = "failed"
        self.job["error_message"] = error_message
        self.job["error_code"] = error_code
        return dict(self.job)

    def fail_expired_job(self, _job_id):
        return dict(self.job)


class CloudTasksDispatcherTests(unittest.TestCase):
    def test_enqueue_uses_deterministic_task_name_and_oidc(self):
        client = FakeTasksClient()
        dispatcher = CloudTasksReportTaskDispatcher(
            project="project-1",
            location="asia-southeast2",
            queue="reports",
            worker_base_url="https://service.run.app/",
            oidc_service_account="task-caller@example.iam.gserviceaccount.com",
            client=client,
        )

        task_name = dispatcher.enqueue(
            {"id": "11111111-2222-3333-4444-555555555555"}
        )

        request = client.created[0]
        task = request["task"]
        self.assertEqual(task_name, task["name"])
        self.assertTrue(
            task_name.endswith(
                "/tasks/report-job-11111111222233334444555555555555"
            )
        )
        self.assertEqual(
            task["http_request"]["url"],
            (
                "https://service.run.app/internal/report-jobs/"
                "11111111-2222-3333-4444-555555555555/execute"
            ),
        )
        self.assertEqual(
            task["http_request"]["oidc_token"]["audience"],
            "https://service.run.app",
        )

    def test_oidc_verification_checks_service_account_identity(self):
        claims = verify_cloud_tasks_oidc(
            "Bearer token-value",
            audience="https://service.run.app",
            service_account="task-caller@example.iam.gserviceaccount.com",
            verifier=lambda token, audience: {
                "email": "task-caller@example.iam.gserviceaccount.com",
                "email_verified": True,
                "aud": audience,
            },
        )
        self.assertEqual(
            claims["email"],
            "task-caller@example.iam.gserviceaccount.com",
        )

        with self.assertRaises(ReportTaskAuthenticationError):
            verify_cloud_tasks_oidc(
                "Bearer token-value",
                audience="https://service.run.app",
                service_account="task-caller@example.iam.gserviceaccount.com",
                verifier=lambda token, audience: {
                    "email": "other@example.iam.gserviceaccount.com",
                    "email_verified": True,
                },
            )


class QStashDispatcherTests(unittest.TestCase):
    def test_enqueue_uses_fifo_queue_and_returns_message_id(self):
        client = FakeQStashClient()
        dispatcher = QStashReportTaskDispatcher(
            token="qstash-token",
            queue="report-generation-staging",
            worker_base_url="https://ai-report.example.com/",
            retries=2,
            timeout="14m",
            client=client,
        )

        message_id = dispatcher.enqueue({"id": "job-1"})

        self.assertEqual(message_id, "msg_report_job_1")
        self.assertEqual(
            client.message.enqueued,
            [
                {
                    "queue": "report-generation-staging",
                    "url": (
                        "https://ai-report.example.com/internal/"
                        "report-jobs/job-1/execute"
                    ),
                    "body": {"job_id": "job-1"},
                    "retries": 2,
                    "timeout": "14m",
                    "label": "report-generation",
                }
            ],
        )

    def test_cancel_deletes_qstash_message(self):
        client = FakeQStashClient()
        dispatcher = QStashReportTaskDispatcher(
            token="qstash-token",
            queue="report-generation-staging",
            worker_base_url="https://ai-report.example.com",
            client=client,
        )

        self.assertTrue(dispatcher.cancel("msg_report_job_1"))
        self.assertEqual(
            client.message.cancelled,
            ["msg_report_job_1"],
        )

    def test_signature_verification_uses_raw_body_and_public_url(self):
        receiver = FakeQStashReceiver()

        verified = verify_qstash_signature(
            "signed-request",
            body=b'{"job_id":"job-1"}',
            url=(
                "https://ai-report.example.com/internal/"
                "report-jobs/job-1/execute"
            ),
            current_signing_key="current-key",
            next_signing_key="next-key",
            receiver=receiver,
        )

        self.assertTrue(verified)
        self.assertEqual(
            receiver.requests,
            [
                {
                    "body": '{"job_id":"job-1"}',
                    "signature": "signed-request",
                    "url": (
                        "https://ai-report.example.com/internal/"
                        "report-jobs/job-1/execute"
                    ),
                }
            ],
        )

        with self.assertRaises(ReportTaskAuthenticationError):
            verify_qstash_signature(
                "invalid-request",
                body="{}",
                url="https://ai-report.example.com/internal/worker",
                current_signing_key="current-key",
                next_signing_key="next-key",
                receiver=FakeQStashReceiver(valid=False),
            )


class ReportJobWorkerTests(unittest.TestCase):
    def test_worker_completes_and_records_presentation_checkpoint(self):
        repository = FakeJobRepository()

        def generator(client_id, period_id, **kwargs):
            kwargs["on_stage"]("slides")
            kwargs["on_presentation_created"](
                {
                    "presentation_id": "presentation-1",
                    "presentation_url": "https://slides/presentation-1",
                    "report_name": "Report 1",
                }
            )
            return {
                "status": "completed",
                "presentation_id": "presentation-1",
                "presentation_url": "https://slides/presentation-1",
                "report_name": "Report 1",
                "gemini_usage": {"total_tokens": 123},
            }

        result = ReportJobWorker(repository, generator).execute("job-1")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["presentation_id"], "presentation-1")
        self.assertEqual(len(repository.recorded_presentations), 1)

    def test_worker_passes_existing_presentation_to_retry(self):
        repository = FakeJobRepository(presentation_id="presentation-existing")
        received = {}

        def generator(client_id, period_id, **kwargs):
            received.update(kwargs)
            return {
                "status": "completed",
                "presentation_id": kwargs["existing_presentation_id"],
                "presentation_url": "https://slides/existing",
                "report_name": kwargs["existing_report_name"],
            }

        ReportJobWorker(repository, generator).execute("job-1")

        self.assertEqual(
            received["existing_presentation_id"],
            "presentation-existing",
        )
        self.assertEqual(received["existing_report_name"], "Existing report")

    def test_worker_finishes_cooperative_cancellation(self):
        repository = FakeJobRepository()

        def generator(client_id, period_id, **kwargs):
            repository.job["status"] = "cancel_requested"
            if kwargs["should_cancel"]():
                raise ReportGenerationCancelledError("cancelled")
            return {}

        result = ReportJobWorker(repository, generator).execute("job-1")

        self.assertEqual(result["status"], "cancelled")

    def test_hard_cancel_stops_blocking_generator_within_budget(self):
        repository = FakeJobRepository()
        worker = ReportJobWorker(
            repository,
            blocking_generator,
            hard_cancel=True,
            cancel_poll_seconds=0.1,
            cancel_grace_seconds=0.2,
            process_start_method="spawn",
        )
        result_holder = {}

        def execute():
            result_holder["result"] = worker.execute("job-1")

        started_at = time.monotonic()
        thread = threading.Thread(target=execute)
        thread.start()
        deadline = time.monotonic() + 5
        while (
            repository.job["current_stage"] != "analysis_blocking_test"
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        repository.job["status"] = "cancel_requested"
        thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(result_holder["result"]["status"], "cancelled")
        self.assertLess(time.monotonic() - started_at, 4)

    def test_hard_cancel_trashes_partial_presentation(self):
        repository = FakeJobRepository()
        cleanup = Mock(
            return_value={
                "success": True,
                "action": "trashed",
                "presentation_id": "presentation-partial",
            }
        )
        worker = ReportJobWorker(
            repository,
            presentation_then_block_generator,
            hard_cancel=True,
            cancel_poll_seconds=0.1,
            cancel_grace_seconds=0.2,
            process_start_method="spawn",
            presentation_cleanup=cleanup,
        )
        result_holder = {}

        thread = threading.Thread(
            target=lambda: result_holder.update(
                result=worker.execute("job-1")
            )
        )
        thread.start()
        deadline = time.monotonic() + 5
        while (
            not repository.recorded_presentations
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        repository.job["status"] = "cancel_requested"
        thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        cleanup.assert_called_once_with(
            "presentation-partial",
            "Partial report",
        )
        self.assertEqual(result_holder["result"]["status"], "cancelled")
        self.assertIsNone(result_holder["result"]["presentation_id"])

    def test_retryable_failure_returns_non_success_signal(self):
        repository = FakeJobRepository()

        def generator(client_id, period_id, **kwargs):
            raise BrokenPipeError(32, "Broken pipe")

        with self.assertRaises(RetryableReportJobError):
            ReportJobWorker(repository, generator).execute("job-1")

        self.assertEqual(repository.job["status"], "retrying")
        self.assertEqual(repository.job["attempt_count"], 1)

    def test_duplicate_delivery_does_not_start_second_generator(self):
        repository = FakeJobRepository(status="running")
        repository.job["attempt_count"] = 1

        def reject_claim(_job_id, *, lease_seconds):
            from dashboard.repositories.report_job_repository import (
                ReportJobTransitionError,
            )

            raise ReportJobTransitionError(repository.get_job("job-1"), "running")

        repository.claim_job = reject_claim
        generator = Mock()

        with self.assertRaises(ReportJobAlreadyRunningError):
            ReportJobWorker(repository, generator).execute("job-1")

        generator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
