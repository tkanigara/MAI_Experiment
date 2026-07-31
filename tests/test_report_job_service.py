from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.report_job_repository import (
    ReportJobTransitionError,
)
from dashboard.services.report_jobs import (
    LocalReportTaskDispatcher,
    ReportJobService,
    ReportQueueUnavailableError,
    ReportTaskDispatchError,
    UnconfiguredReportTaskDispatcher,
)


class FakeDispatcher:
    def __init__(self):
        self.configured = True
        self.enqueued = []
        self.cancelled = []
        self.activated = []
        self.enqueue_error = None

    def enqueue(self, job: dict) -> str:
        if self.enqueue_error:
            raise self.enqueue_error
        self.enqueued.append(job)
        return f"queues/report-jobs/tasks/{job['id']}"

    def cancel(self, task_name: str) -> bool:
        self.cancelled.append(task_name)
        return True

    def activate(self, task_name: str) -> None:
        self.activated.append(task_name)


class ReportJobServiceTests(unittest.TestCase):
    def test_create_job_enqueues_and_persists_task_name(self):
        repository = Mock()
        repository.create_job.return_value = {
            "id": "job-1",
            "status": "queued",
        }
        repository.set_cloud_task_name.return_value = {
            "id": "job-1",
            "status": "queued",
            "cloud_task_name": "queues/report-jobs/tasks/job-1",
        }
        dispatcher = FakeDispatcher()
        service = ReportJobService(repository, dispatcher)

        result = service.create_job("client-1", "period-1")

        self.assertEqual(
            result["cloud_task_name"],
            "queues/report-jobs/tasks/job-1",
        )
        repository.set_cloud_task_name.assert_called_once_with(
            "job-1",
            "queues/report-jobs/tasks/job-1",
        )
        self.assertEqual(
            dispatcher.activated,
            ["queues/report-jobs/tasks/job-1"],
        )

    def test_local_dispatcher_runs_only_after_job_is_activated(self):
        processed = Event()
        received = []

        def execute(job_id):
            received.append(job_id)
            processed.set()
            return {"status": "completed"}

        dispatcher = LocalReportTaskDispatcher(
            execute,
            retry_delay_seconds=0,
        )
        task_name = dispatcher.enqueue({"id": "job-local-1"})

        self.assertFalse(processed.wait(0.05))
        dispatcher.activate(task_name)
        self.assertTrue(processed.wait(1))
        self.assertEqual(received, ["job-local-1"])

    def test_local_dispatcher_can_cancel_before_activation(self):
        processed = Event()
        dispatcher = LocalReportTaskDispatcher(
            lambda _job_id: processed.set(),
            retry_delay_seconds=0,
        )
        task_name = dispatcher.enqueue({"id": "job-local-2"})

        self.assertTrue(dispatcher.cancel(task_name))
        dispatcher.activate(task_name)
        self.assertFalse(processed.wait(0.05))

    def test_unconfigured_dispatcher_rejects_before_database_insert(self):
        repository = Mock()
        service = ReportJobService(
            repository,
            UnconfiguredReportTaskDispatcher(),
        )

        with self.assertRaises(ReportQueueUnavailableError):
            service.create_job("client-1", "period-1")

        repository.create_job.assert_not_called()

    def test_dispatch_failure_marks_job_failed(self):
        repository = Mock()
        repository.create_job.return_value = {
            "id": "job-1",
            "status": "queued",
        }
        dispatcher = FakeDispatcher()
        dispatcher.enqueue_error = RuntimeError("Cloud Tasks unavailable")
        service = ReportJobService(repository, dispatcher)

        with self.assertRaises(ReportTaskDispatchError):
            service.create_job("client-1", "period-1")

        repository.fail_job.assert_called_once_with(
            "job-1",
            "Failed to enqueue report generation.",
            error_code="QUEUE_DISPATCH_FAILED",
        )

    def test_cancel_deletes_task_and_updates_database_state(self):
        repository = Mock()
        repository.get_job.return_value = {
            "id": "job-1",
            "status": "queued",
            "cloud_task_name": "queues/report-jobs/tasks/job-1",
        }
        repository.request_cancel.return_value = {
            "id": "job-1",
            "status": "cancelled",
        }
        dispatcher = FakeDispatcher()
        service = ReportJobService(repository, dispatcher)

        result = service.cancel_job(
            "job-1",
            reason="Clicked by mistake",
        )

        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(
            dispatcher.cancelled,
            ["queues/report-jobs/tasks/job-1"],
        )
        repository.request_cancel.assert_called_once_with(
            "job-1",
            cancelled_by=None,
            reason="Clicked by mistake",
        )

    def test_completed_job_cannot_be_retried(self):
        repository = Mock()
        completed = {
            "id": "job-1",
            "status": "completed",
            "client_id": "client-1",
            "report_period_id": "period-1",
        }
        repository.get_job.return_value = completed
        service = ReportJobService(repository, FakeDispatcher())

        with self.assertRaises(ReportJobTransitionError):
            service.retry_job("job-1")

        repository.create_job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
