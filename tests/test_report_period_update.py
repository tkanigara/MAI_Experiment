from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, Mock, patch

from fastapi.testclient import TestClient

from dashboard import main
from dashboard.repositories.dashboard_repository import (
    DashboardRepository,
    ReportPeriodAlreadyExistsError,
)


class FakeMappingResult:
    def __init__(self, *, first=None):
        self._first = first

    def mappings(self):
        return self

    def first(self):
        return self._first


class ReportPeriodUpdateTests(unittest.TestCase):
    def setUp(self):
        self.repository = object.__new__(DashboardRepository)
        self.connection = MagicMock()
        self.engine = MagicMock()
        self.engine.begin.return_value.__enter__.return_value = self.connection
        self.repository.engine = self.engine

    @patch("dashboard.repositories.dashboard_repository.lock_report_period")
    def test_report_month_is_updated_without_changing_period_id(self, lock_period):
        lock_period.return_value = {
            "id": "period-1",
            "period_label": "July 2026",
        }
        self.connection.execute.side_effect = [
            FakeMappingResult(first=None),
            FakeMappingResult(
                first={
                    "id": "period-1",
                    "period_label": "August 2026",
                    "period_start": date(2026, 8, 1),
                    "period_end": date(2026, 8, 31),
                }
            ),
        ]

        result = self.repository.update_report_period(
            "client-1",
            "period-1",
            {"month_slug": "august-2026"},
        )

        self.assertEqual(result["id"], "period-1")
        self.assertEqual(result["label"], "August 2026")
        self.assertEqual(result["slug"], "august-2026")
        update_sql = str(self.connection.execute.call_args_list[1].args[0])
        self.assertIn("UPDATE report_periods", update_sql)
        self.assertNotIn("DELETE FROM report_periods", update_sql)

    @patch("dashboard.repositories.dashboard_repository.lock_report_period")
    def test_existing_target_month_is_rejected_before_update(self, lock_period):
        lock_period.return_value = {
            "id": "period-1",
            "period_label": "July 2026",
        }
        self.connection.execute.return_value = FakeMappingResult(
            first={
                "id": "period-2",
                "period_label": "August 2026",
                "period_start": date(2026, 8, 1),
                "period_end": date(2026, 8, 31),
            }
        )

        with self.assertRaises(ReportPeriodAlreadyExistsError) as context:
            self.repository.update_report_period(
                "client-1",
                "period-1",
                {"month_slug": "august-2026"},
            )

        self.assertEqual(context.exception.code, "REPORT_PERIOD_ALREADY_EXISTS")
        self.assertEqual(context.exception.period["id"], "period-2")
        self.assertEqual(self.connection.execute.call_count, 1)

    def test_missing_month_slug_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "month_slug is required"):
            self.repository.update_report_period(
                "client-1",
                "period-1",
                {},
            )


class ReportPeriodUpdateApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_api_returns_conflict_when_target_month_exists(self):
        repository = Mock()
        repository.update_report_period.side_effect = (
            ReportPeriodAlreadyExistsError(
                {
                    "id": "period-2",
                    "period_label": "August 2026",
                    "period_start": date(2026, 8, 1),
                },
                "August 2026",
            )
        )

        with patch.object(main, "repository", repository):
            response = self.client.put(
                "/api/clients/client-1/report-periods/period-1",
                json={"month_slug": "august-2026"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["code"],
            "REPORT_PERIOD_ALREADY_EXISTS",
        )
        self.assertEqual(response.json()["period"]["id"], "period-2")

    def test_api_updates_report_month(self):
        repository = Mock()
        repository.update_report_period.return_value = {
            "id": "period-1",
            "label": "August 2026",
            "slug": "august-2026",
        }

        with patch.object(main, "repository", repository):
            response = self.client.put(
                "/api/clients/client-1/report-periods/period-1",
                json={"month_slug": "august-2026"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "august-2026")
        repository.update_report_period.assert_called_once_with(
            "client-1",
            "period-1",
            {"month_slug": "august-2026"},
        )

    def test_csv_update_passes_existing_period_id_to_repository(self):
        repository = Mock()
        repository.import_csv_report.return_value = {
            "period": {
                "id": "period-1",
                "label": "August 2026",
                "slug": "august-2026",
            },
            "summary": {},
            "files": [],
        }

        with patch.object(main, "repository", repository):
            response = self.client.post(
                "/api/import/csv",
                data={
                    "client_id": "client-1",
                    "period_id": "period-1",
                    "month_slug": "august-2026",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = repository.import_csv_report.call_args.args[0]
        self.assertEqual(payload["client_id"], "client-1")
        self.assertEqual(payload["period_id"], "period-1")
        self.assertEqual(payload["month_slug"], "august-2026")

    def test_csv_update_returns_conflict_for_existing_target_month(self):
        repository = Mock()
        repository.import_csv_report.side_effect = (
            ReportPeriodAlreadyExistsError(
                {
                    "id": "period-2",
                    "period_label": "August 2026",
                    "period_start": date(2026, 8, 1),
                },
                "August 2026",
            )
        )

        with patch.object(main, "repository", repository):
            response = self.client.post(
                "/api/import/csv",
                data={
                    "client_id": "client-1",
                    "period_id": "period-1",
                    "month_slug": "august-2026",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["code"],
            "REPORT_PERIOD_ALREADY_EXISTS",
        )


if __name__ == "__main__":
    unittest.main()
