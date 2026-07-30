from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import main
from dashboard.services.report_jobs import (
    ReportQueueUnavailableError,
    ReportTaskAuthenticationError,
)


class ReportJobApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_create_job_returns_accepted(self):
        service = Mock()
        service.create_job.return_value = {
            "id": "job-1",
            "status": "queued",
        }

        with patch.object(main, "report_jobs", service):
            response = self.client.post(
                "/api/report-jobs",
                json={
                    "client_id": "client-1",
                    "period_id": "period-1",
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        service.create_job.assert_called_once_with(
            "client-1",
            "period-1",
            dry_run=False,
        )

    def test_unconfigured_queue_returns_service_unavailable(self):
        service = Mock()
        service.create_job.side_effect = ReportQueueUnavailableError(
            "Report queue is not configured in this environment."
        )

        with patch.object(main, "report_jobs", service):
            response = self.client.post(
                "/api/report-jobs",
                json={
                    "client_id": "client-1",
                    "period_id": "period-1",
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["error"])

    def test_history_returns_jobs_for_period(self):
        service = Mock()
        service.history.return_value = [
            {"id": "job-2", "status": "completed"},
            {"id": "job-1", "status": "failed"},
        ]

        with patch.object(main, "report_jobs", service):
            response = self.client.get(
                "/api/clients/client-1/report-periods/period-1/report-jobs",
                params={"limit": 10},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [job["id"] for job in response.json()],
            ["job-2", "job-1"],
        )
        service.history.assert_called_once_with(
            "client-1",
            "period-1",
            limit=10,
        )

    def test_global_history_returns_jobs_across_clients(self):
        service = Mock()
        service.all_history.return_value = [
            {"id": "job-2", "client_name_snapshot": "Client B"},
            {"id": "job-1", "client_name_snapshot": "Client A"},
        ]

        with patch.object(main, "report_jobs", service):
            response = self.client.get(
                "/api/report-jobs",
                params={"limit": 50},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        service.all_history.assert_called_once_with(limit=50)

    def test_client_history_returns_jobs_across_periods(self):
        service = Mock()
        service.client_history.return_value = [
            {"id": "job-2", "period_label_snapshot": "July 2026"},
            {"id": "job-1", "period_label_snapshot": "June 2026"},
        ]

        with patch.object(main, "report_jobs", service):
            response = self.client.get(
                "/api/clients/client-1/report-jobs",
                params={"limit": 50},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [job["period_label_snapshot"] for job in response.json()],
            ["July 2026", "June 2026"],
        )
        service.client_history.assert_called_once_with(
            "client-1",
            limit=50,
        )

    def test_cancel_returns_updated_job(self):
        service = Mock()
        service.cancel_job.return_value = {
            "id": "job-1",
            "status": "cancel_requested",
        }

        with patch.object(main, "report_jobs", service):
            response = self.client.post(
                "/api/report-jobs/job-1/cancel",
                json={"reason": "Clicked by mistake"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancel_requested")
        service.cancel_job.assert_called_once_with(
            "job-1",
            reason="Clicked by mistake",
        )

    def test_internal_worker_rejects_invalid_task_identity(self):
        with patch.object(
            main,
            "verify_cloud_tasks_oidc",
            side_effect=ReportTaskAuthenticationError("invalid task token"),
        ):
            response = self.client.post(
                "/internal/report-jobs/job-1/execute",
                headers={"Authorization": "Bearer invalid"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertIn("invalid task token", response.json()["error"])

    def test_internal_worker_executes_after_oidc_verification(self):
        worker = Mock()
        worker.execute.return_value = {
            "id": "job-1",
            "status": "completed",
        }

        with (
            patch.object(main, "report_job_worker", worker),
            patch.object(main, "verify_cloud_tasks_oidc") as verify,
        ):
            response = self.client.post(
                "/internal/report-jobs/job-1/execute",
                headers={"Authorization": "Bearer valid"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        verify.assert_called_once_with("Bearer valid")
        worker.execute.assert_called_once_with("job-1")


if __name__ == "__main__":
    unittest.main()
