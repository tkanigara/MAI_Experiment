from __future__ import annotations

import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.report_job_repository import (
    ActiveReportJobError,
    ReportJobRepository,
    ReportJobTransitionError,
)


class FakeMappingResult:
    def __init__(self, *, first=None, one=None, rows=None):
        self._first = first
        self._one = one
        self._rows = list(rows or [])

    def mappings(self):
        return self

    def first(self):
        return self._first

    def one(self):
        return self._one

    def __iter__(self):
        return iter(self._rows)


class FakeConnection:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((str(statement), parameters or {}))
        if not self.results:
            raise AssertionError("Unexpected database execute call.")
        return self.results.pop(0)


class FakeEngine:
    def __init__(self, *connections):
        self.connections = list(connections)

    @contextmanager
    def begin(self):
        if not self.connections:
            raise AssertionError("Unexpected database transaction.")
        yield self.connections.pop(0)


class ReportJobRepositoryTests(unittest.TestCase):
    def test_create_job_uses_client_and_period_snapshots(self):
        context = {
            "client_id": "client-1",
            "client_name": "PAR",
            "report_period_id": "period-1",
            "period_label": "July 2026",
        }
        created = {
            "id": "job-1",
            "status": "queued",
            "client_name_snapshot": "PAR",
            "period_label_snapshot": "July 2026",
        }
        connection = FakeConnection(
            [
                FakeMappingResult(first=context),
                FakeMappingResult(
                    first={
                        "id": "period-1",
                        "client_id": "client-1",
                        "period_label": "July 2026",
                    }
                ),
                FakeMappingResult(first=None),
                FakeMappingResult(one=created),
            ]
        )
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.create_job(
            "client-1",
            "period-1",
            requested_by="  developer@mai.co.id  ",
        )

        self.assertEqual(result["id"], "job-1")
        self.assertIn("FOR UPDATE", connection.calls[1][0])
        _statement, parameters = connection.calls[3]
        self.assertEqual(parameters["client_name"], "PAR")
        self.assertEqual(parameters["period_label"], "July 2026")
        self.assertEqual(parameters["requested_by"], "developer@mai.co.id")
        self.assertEqual(parameters["max_attempts"], 3)
        self.assertIn(
            "SELECT presentation_id",
            connection.calls[3][0],
        )

    def test_create_job_keeps_existing_active_job_conflict_contract(self):
        context = {
            "client_id": "client-1",
            "client_name": "PAR",
            "report_period_id": "period-1",
            "period_label": "July 2026",
        }
        active_job = {
            "id": "job-active",
            "client_id": "client-1",
            "report_period_id": "period-1",
            "status": "running",
        }
        connection = FakeConnection(
            [
                FakeMappingResult(first=context),
                FakeMappingResult(first={"id": "period-1"}),
                FakeMappingResult(first=active_job),
            ]
        )
        repository = ReportJobRepository(FakeEngine(connection))

        with self.assertRaises(ActiveReportJobError) as context_manager:
            repository.create_job("client-1", "period-1")

        self.assertEqual(context_manager.exception.job["id"], "job-active")
        self.assertEqual(len(connection.calls), 3)

    def test_claim_job_sets_a_bounded_lease(self):
        running = {
            "id": "job-1",
            "status": "running",
            "attempt_count": 1,
        }
        connection = FakeConnection([FakeMappingResult(first=running)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.claim_job("job-1", lease_seconds=600)

        self.assertEqual(result["status"], "running")
        statement, parameters = connection.calls[0]
        self.assertIn("attempt_count = attempt_count + 1", statement)
        self.assertIn("status IN ('queued', 'retrying')", statement)
        self.assertIn("lease_expires_at <= now()", statement)
        self.assertEqual(parameters["lease_seconds"], 600)

    def test_complete_job_serializes_usage_and_result_metadata(self):
        completed = {
            "id": "job-1",
            "status": "completed",
            "presentation_url": "https://docs.google.com/presentation/d/test",
        }
        connection = FakeConnection([FakeMappingResult(first=completed)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.complete_job(
            "job-1",
            presentation_id="presentation-1",
            presentation_url=completed["presentation_url"],
            gemini_usage={"input_tokens": 100, "output_tokens": 25},
            result_metadata={"model": "gemini-3.1-flash-lite"},
        )

        self.assertEqual(result["status"], "completed")
        _statement, parameters = connection.calls[0]
        self.assertEqual(
            json.loads(parameters["gemini_usage"]),
            {"input_tokens": 100, "output_tokens": 25},
        )
        self.assertEqual(
            json.loads(parameters["result_metadata"]),
            {"model": "gemini-3.1-flash-lite"},
        )

    def test_invalid_transition_reports_current_status(self):
        update_connection = FakeConnection([FakeMappingResult(first=None)])
        lookup_connection = FakeConnection(
            [FakeMappingResult(first={"id": "job-1", "status": "completed"})]
        )
        repository = ReportJobRepository(
            FakeEngine(update_connection, lookup_connection)
        )

        with self.assertRaises(ReportJobTransitionError) as context:
            repository.claim_job("job-1")

        self.assertEqual(context.exception.job["status"], "completed")
        self.assertEqual(context.exception.target_status, "running")

    def test_cancel_queued_job_finishes_immediately(self):
        cancelled = {
            "id": "job-1",
            "status": "cancelled",
            "cancel_reason": "Clicked by mistake",
        }
        connection = FakeConnection([FakeMappingResult(first=cancelled)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.request_cancel(
            "job-1",
            cancelled_by="developer@mai.co.id",
            reason="Clicked by mistake",
        )

        self.assertEqual(result["status"], "cancelled")
        statement, parameters = connection.calls[0]
        self.assertIn(
            "WHEN status IN ('queued', 'retrying') THEN 'cancelled'",
            statement,
        )
        self.assertEqual(parameters["cancel_reason"], "Clicked by mistake")
        self.assertEqual(
            parameters["cancelled_by"],
            "developer@mai.co.id",
        )

    def test_running_job_moves_to_cancel_requested(self):
        cancel_requested = {
            "id": "job-1",
            "status": "cancel_requested",
        }
        request_connection = FakeConnection(
            [FakeMappingResult(first=cancel_requested)]
        )
        finish_connection = FakeConnection(
            [FakeMappingResult(first={"id": "job-1", "status": "cancelled"})]
        )
        repository = ReportJobRepository(
            FakeEngine(request_connection, finish_connection)
        )

        requested = repository.request_cancel("job-1")
        finished = repository.mark_cancelled("job-1")

        self.assertEqual(requested["status"], "cancel_requested")
        self.assertEqual(finished["status"], "cancelled")
        self.assertIn(
            "cancel_latency_seconds",
            finish_connection.calls[0][0],
        )

    def test_presentation_checkpoint_survives_cancel_race(self):
        row = {
            "id": "job-1",
            "status": "cancel_requested",
            "presentation_id": "presentation-partial",
        }
        connection = FakeConnection([FakeMappingResult(first=row)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.record_presentation(
            "job-1",
            presentation_id="presentation-partial",
            presentation_url="https://slides/presentation-partial",
            report_name="Partial report",
        )

        self.assertEqual(result["presentation_id"], "presentation-partial")
        statement, _parameters = connection.calls[0]
        self.assertIn(
            "status IN ('running', 'cancel_requested')",
            statement,
        )

    def test_cancellation_cleanup_can_clear_trashed_presentation(self):
        row = {
            "id": "job-1",
            "status": "cancelled",
            "presentation_id": None,
        }
        connection = FakeConnection([FakeMappingResult(first=row)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.record_cancellation_cleanup(
            "job-1",
            {
                "success": True,
                "action": "trashed",
                "presentation_id": "presentation-partial",
            },
            clear_presentation=True,
        )

        self.assertIsNone(result["presentation_id"])
        statement, parameters = connection.calls[0]
        self.assertIn("cancellation_cleanup", statement)
        self.assertTrue(parameters["clear_presentation"])

    def test_history_limit_is_capped(self):
        rows = [
            {"id": "job-2", "status": "completed"},
            {"id": "job-1", "status": "failed"},
        ]
        connection = FakeConnection([FakeMappingResult(rows=rows)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.list_for_period(
            "client-1",
            "period-1",
            limit=500,
        )

        self.assertEqual([row["id"] for row in result], ["job-2", "job-1"])
        _statement, parameters = connection.calls[0]
        self.assertEqual(parameters["limit"], 100)

    def test_client_history_filters_by_client(self):
        rows = [
            {
                "id": "job-2",
                "client_id": "client-1",
                "period_label_snapshot": "July 2026",
            },
        ]
        connection = FakeConnection([FakeMappingResult(rows=rows)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.list_for_client("client-1", limit=25)

        self.assertEqual(result, rows)
        statement, parameters = connection.calls[0]
        self.assertIn("WHERE client_id = :client_id", statement)
        self.assertEqual(parameters["client_id"], "client-1")
        self.assertEqual(parameters["limit"], 25)

    def test_global_history_limit_is_capped(self):
        rows = [
            {"id": "job-2", "client_name_snapshot": "Client B"},
            {"id": "job-1", "client_name_snapshot": "Client A"},
        ]
        connection = FakeConnection([FakeMappingResult(rows=rows)])
        repository = ReportJobRepository(FakeEngine(connection))

        result = repository.list_all(limit=500)

        self.assertEqual(result, rows)
        statement, parameters = connection.calls[0]
        self.assertNotIn("WHERE client_id", statement)
        self.assertEqual(parameters["limit"], 100)


if __name__ == "__main__":
    unittest.main()
