from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.services.report_jobs import (
    CloudTasksReportTaskDispatcher,
    ReportGenerationCancelledError,
    ReportJobAlreadyRunningError,
    ReportJobWorker,
    ReportTaskAuthenticationError,
    RetryableReportJobError,
    verify_cloud_tasks_oidc,
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
