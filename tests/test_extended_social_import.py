from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from dashboard.repositories.dashboard_repository import DashboardRepository


class ExtendedSocialImportTests(unittest.TestCase):
    def setUp(self):
        self.repository = object.__new__(DashboardRepository)
        self.data = {
            "existing_report_id": "report-id",
            "content_type_breakdown": '{"photo": 3}',
        }

    def executed_sql(self, data: dict) -> str:
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.one.return_value = {
            "id": "report-id"
        }
        self.repository.upsert_extended_social_report(
            conn,
            "linkedin_reports",
            data,
        )
        return str(conn.execute.call_args.args[0])

    def test_existing_report_casts_content_breakdown_before_coalesce(self):
        sql = self.executed_sql(self.data)

        self.assertIn(
            "CAST(:content_type_breakdown AS JSONB)",
            sql,
        )
        self.assertNotIn(
            "WHEN :content_type_breakdown IS NOT NULL",
            sql,
        )

    def test_insert_conflict_path_casts_content_breakdown_before_coalesce(self):
        sql = self.executed_sql(
            {**self.data, "existing_report_id": None}
        )

        self.assertIn(
            "CAST(:content_type_breakdown AS JSONB)",
            sql,
        )
        self.assertNotIn(
            "WHEN :content_type_breakdown IS NOT NULL",
            sql,
        )


if __name__ == "__main__":
    unittest.main()
