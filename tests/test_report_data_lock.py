from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.report_data_lock import (
    ReportDataLockedError,
    lock_report_period,
)


class FakeMappingResult:
    def __init__(self, *, first=None):
        self._first = first

    def mappings(self):
        return self

    def first(self):
        return self._first


class FakeConnection:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((str(statement), parameters or {}))
        if not self.results:
            raise AssertionError("Unexpected database execute call.")
        return self.results.pop(0)


class ReportDataLockTests(unittest.TestCase):
    def test_period_is_locked_before_active_job_is_checked(self):
        period = {
            "id": "period-1",
            "client_id": "client-1",
            "period_label": "July 2026",
        }
        connection = FakeConnection(
            [
                FakeMappingResult(first=period),
                FakeMappingResult(first=None),
            ]
        )

        result = lock_report_period(connection, "client-1", "period-1")

        self.assertEqual(result["id"], "period-1")
        self.assertIn("FOR UPDATE", connection.calls[0][0])
        self.assertIn("status IN", connection.calls[1][0])

    def test_active_job_blocks_report_data_change(self):
        active_job = {
            "id": "job-1",
            "client_id": "client-1",
            "report_period_id": "period-1",
            "status": "running",
            "period_label_snapshot": "July 2026",
        }
        connection = FakeConnection(
            [
                FakeMappingResult(first={"id": "period-1"}),
                FakeMappingResult(first=active_job),
            ]
        )

        with self.assertRaises(ReportDataLockedError) as context:
            lock_report_period(connection, "client-1", "period-1")

        self.assertEqual(context.exception.code, "REPORT_PERIOD_LOCKED")
        self.assertEqual(context.exception.job["id"], "job-1")


if __name__ == "__main__":
    unittest.main()
