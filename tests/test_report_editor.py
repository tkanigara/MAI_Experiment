from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.services.report_editor import (
    is_ai_placeholder,
    parse_editor_value,
    placeholder_aliases,
    scaled_rate,
    trend_placeholder_aliases,
    validate_public_url,
)
from dashboard.services.report_data_quality import (
    build_report_quality,
    calculated_rate,
    consecutive_previous_trend,
)


class ReportEditorUnitTests(unittest.TestCase):
    def test_ai_insight_placeholders_are_read_only(self):
        self.assertTrue(is_ai_placeholder("{{IG_KPI_ANALYSIS}}"))
        self.assertTrue(
            is_ai_placeholder("{{FB_INSIGHT_FOLLOWERS_GROWTH_TEXT}}")
        )
        self.assertFalse(is_ai_placeholder("{{IG_TOTAL_FOLLOWERS}}"))

    def test_canonical_fields_expand_to_aliases(self):
        aliases = placeholder_aliases("instagram", "follower_growth")
        self.assertIn("{{IG_NET_GROWTH}}", aliases)
        self.assertIn("{{IG_FOLLOWERS_GROWTH}}", aliases)
        self.assertIn(
            "{{LK_TOTAL_FOLLOWERS}}",
            placeholder_aliases("linkedin", "total_followers"),
        )
        self.assertIn(
            "{{TH_TOTAL_FOLLOWERS}}",
            placeholder_aliases("threads", "total_followers"),
        )
        trend_aliases = trend_placeholder_aliases(
            "youtube",
            2,
            "audience_total",
        )
        self.assertIn("{{YT_M2_TOTAL_SUBSCRIBERS}}", trend_aliases)

    def test_private_urls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Private or local"):
            validate_public_url("http://127.0.0.1/image.png")
        with self.assertRaisesRegex(ValueError, "Private or local"):
            validate_public_url("http://localhost/image.png")

    def test_numeric_and_json_values_are_parsed(self):
        self.assertEqual(parse_editor_value("1,234.5", "number"), 1234.5)
        self.assertEqual(
            parse_editor_value('{"female": 60}', "json"),
            {"female": 60},
        )

    def test_engagement_rate_scales_with_engagement_delta(self):
        self.assertEqual(
            scaled_rate("1.14", "825", "925", "11354"),
            Decimal("1.278181818181818181818181818"),
        )

    def test_engagement_rate_uses_audience_as_fallback(self):
        self.assertEqual(
            scaled_rate(None, 0, 100, 1000),
            Decimal("10.0"),
        )

    def test_quality_uses_only_the_immediately_previous_month(self):
        trends = [
            {
                "source_period_id": "july",
                "period_start": date(2026, 7, 1),
                "report_id": "report-july",
            },
            {
                "source_period_id": "may",
                "period_start": date(2026, 5, 1),
                "report_id": "report-may",
            },
        ]
        self.assertIsNone(consecutive_previous_trend(trends, "july"))

    def test_report_quality_exposes_growth_and_rate_alternatives(self):
        report = {
            "total_followers": 1100,
            "follower_growth": 100,
            "follower_growth_rate": 10,
            "follows": 120,
            "unfollows": 10,
            "total_engagement": 220,
            "engagement_rate": 5,
            "reach": 550,
            "likes": 100,
            "comments": 50,
            "shares": 30,
            "saves": 20,
            "reposts": 20,
            "total_posts": 1,
            "reels_posts": 1,
            "carousel_posts": 0,
            "single_posts": 0,
        }
        quality = build_report_quality(
            platform="instagram",
            report=report,
            trends=[
                {
                    "source_period_id": "july",
                    "period_start": date(2026, 7, 1),
                    "report_id": "report-july",
                    "audience_total": 1100,
                },
                {
                    "source_period_id": "june",
                    "period_start": date(2026, 6, 1),
                    "report_id": "report-june",
                    "audience_total": 1000,
                },
            ],
            period_id="july",
            all_content_count=1,
            fanpage_engagement_rate=5,
        )

        growth_codes = {
            check["code"]
            for check in quality["follower_growth"]["quality_checks"]
        }
        self.assertNotIn("GROWTH_PERIOD_DELTA_MISMATCH", growth_codes)
        self.assertIn("GROWTH_FLOW_BALANCE_MISMATCH", growth_codes)
        self.assertEqual(
            quality["follows"]["quality_checks"][0]["issue_id"],
            "instagram:GROWTH_FLOW_BALANCE_MISMATCH",
        )
        self.assertEqual(
            quality["unfollows"]["quality_checks"][0]["issue_id"],
            "instagram:GROWTH_FLOW_BALANCE_MISMATCH",
        )
        self.assertEqual(
            quality["follows"]["value_candidates"][0]["value"],
            110.0,
        )
        self.assertEqual(
            quality["follows"]["quality_checks"][0]["actual_value"],
            120.0,
        )
        self.assertEqual(
            quality["follows"]["quality_checks"][0]["calculated_value"],
            110.0,
        )
        self.assertEqual(
            quality["unfollows"]["value_candidates"][0]["value"],
            20.0,
        )
        rate_candidates = {
            candidate["id"]: candidate
            for candidate in quality["engagement_rate"]["value_candidates"]
        }
        self.assertEqual(rate_candidates["fanpage_karma_rate"]["value"], 5.0)
        self.assertEqual(
            rate_candidates["calculated_rate_by_audience"]["value"],
            20.0,
        )
        self.assertEqual(
            rate_candidates["calculated_rate_by_reach"]["value"],
            40.0,
        )
        rate_issue_id = "instagram:ENGAGEMENT_RATE_DEFINITION_MISMATCH"
        for field_name in (
            "engagement_rate",
            "total_engagement",
            "total_followers",
            "reach",
        ):
            self.assertIn(
                rate_issue_id,
                {
                    check["issue_id"]
                    for check in quality[field_name]["quality_checks"]
                },
            )

    def test_period_growth_warning_marks_every_editable_audience_component(self):
        quality = build_report_quality(
            platform="instagram",
            report={
                "total_followers": 1090,
                "follower_growth": 100,
                "follower_growth_rate": 10,
                "follows": None,
                "unfollows": None,
                "total_engagement": None,
                "engagement_rate": None,
                "reach": None,
                "total_posts": None,
                "reels_posts": None,
                "carousel_posts": None,
                "single_posts": None,
            },
            trends=[
                {
                    "source_period_id": "july",
                    "period_start": date(2026, 7, 1),
                    "report_id": "report-july",
                    "audience_total": 1090,
                },
                {
                    "source_period_id": "june",
                    "period_start": date(2026, 6, 1),
                    "report_id": "report-june",
                    "audience_total": 1000,
                },
            ],
            period_id="july",
            all_content_count=None,
            fanpage_engagement_rate=None,
        )
        issue_id = "instagram:GROWTH_PERIOD_DELTA_MISMATCH"
        self.assertEqual(
            quality["total_followers"]["quality_checks"][0]["issue_id"],
            issue_id,
        )
        historical_key = "historical|june|total_followers"
        self.assertEqual(
            quality[historical_key]["quality_checks"][0]["issue_id"],
            issue_id,
        )
        self.assertEqual(
            quality["total_followers"]["value_candidates"][0]["value"],
            1100.0,
        )
        self.assertEqual(
            quality[historical_key]["value_candidates"][0]["value"],
            990.0,
        )

    def test_missing_rate_denominator_is_unavailable_not_zero(self):
        self.assertIsNone(calculated_rate(10, None))
        self.assertIsNone(calculated_rate(10, 0))

if __name__ == "__main__":
    unittest.main()
