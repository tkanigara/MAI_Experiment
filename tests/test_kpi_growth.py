from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock

from dashboard.repositories.dashboard_repository import dashboard_kpi_results
from dashboard.slides_report import SlidesReportRepository, add_kpi_mapping


class KpiGrowthTests(unittest.TestCase):
    def test_dashboard_followers_kpi_uses_growth_and_ytd_sum(self):
        rows = [
            {
                "metric_name": "followers",
                "actual_month": 1_250,
                "actual_year": 1_250,
                "target_month": 50,
                "target_year": 200,
                "achievement_month": 2_500,
                "achievement_year": 625,
            }
        ]
        report = {
            "period_start": date(2026, 7, 1),
            "total_followers": 1_250,
            "follower_growth": 25,
        }

        results = dashboard_kpi_results(
            "instagram",
            report,
            rows,
            [],
            {"followers": 140},
        )
        followers = next(
            row for row in results if row["metric_name"] == "followers"
        )

        self.assertEqual(followers["actual_month"], 25)
        self.assertEqual(followers["actual_year"], 140)
        self.assertEqual(followers["achievement_month"], 50.0)
        self.assertEqual(followers["achievement_year"], 70.0)

    def test_dashboard_subscribers_kpi_uses_subscriber_growth(self):
        report = {
            "period_start": date(2026, 7, 1),
            "total_subscribers": 9_000,
            "subscriber_growth": 120,
        }

        results = dashboard_kpi_results(
            "youtube",
            report,
            [],
            [],
            {"subscribers": 530},
        )
        subscribers = next(
            row for row in results if row["metric_name"] == "subscribers"
        )

        self.assertEqual(subscribers["actual_month"], 120)
        self.assertEqual(subscribers["actual_year"], 530)

    def test_slide_kpi_placeholders_keep_names_but_use_growth_values(self):
        mapping = {}
        add_kpi_mapping(
            mapping,
            "IG",
            "instagram",
            [
                {
                    "metric_name": "followers",
                    "actual_month": 25,
                    "actual_year": 140,
                    "target_month": 50,
                    "target_year": 200,
                    "achievement_month": None,
                    "achievement_year": None,
                }
            ],
            {"total_followers": 1_250, "follower_growth": 25},
        )

        self.assertEqual(mapping["{{IG_FOL_ACTUAL_MONTH}}"], "25")
        self.assertEqual(mapping["{{IG_FOL_ACTUAL_YEAR}}"], "140")
        self.assertEqual(mapping["{{IG_FOL_PCT_MONTH}}"], "50%")
        self.assertEqual(mapping["{{IG_FOL_PCT_YEAR}}"], "70%")

    def test_slide_repository_replaces_stale_audience_actuals(self):
        result = MagicMock()
        result.scalar_one_or_none.return_value = 530
        conn = MagicMock()
        conn.execute.return_value = result
        rows = [
            {
                "metric_name": "subscribers",
                "actual_month": 9_000,
                "actual_year": 9_000,
                "achievement_month": 900,
                "achievement_year": 900,
            }
        ]
        repository = object.__new__(SlidesReportRepository)

        repository.apply_audience_growth_kpi_actuals(
            conn,
            "client-id",
            {"period_start": date(2026, 7, 1)},
            "youtube",
            "youtube_reports",
            {"total_subscribers": 9_000, "subscriber_growth": 120},
            rows,
        )

        self.assertEqual(rows[0]["actual_month"], 120)
        self.assertEqual(rows[0]["actual_year"], 530)
        self.assertIsNone(rows[0]["achievement_month"])
        self.assertIsNone(rows[0]["achievement_year"])
        sql = str(conn.execute.call_args.args[0])
        self.assertIn("subscriber_growth", sql)


if __name__ == "__main__":
    unittest.main()
