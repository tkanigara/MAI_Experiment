from __future__ import annotations

import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
