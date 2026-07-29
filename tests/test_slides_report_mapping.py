from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.dashboard_repository import post_json
from dashboard.slides_report import (
    COMPETITOR_HIGH_COLOR,
    COMPETITOR_LOW_COLOR,
    SLIDES_IMAGE_REPLACE_METHOD,
    build_mapping,
    competitor_metric_style_mapping,
    image_placeholder_priority,
    is_image_placeholder_key,
    replace_text_placeholders_chunked,
    upload_chart_images,
)


class FakeSlidesService:
    def __init__(self):
        self.batches = []

    def presentations(self):
        return self

    def batchUpdate(self, presentationId, body):
        self.batches.append(body["requests"])
        return self

    def execute(self):
        return {"replies": []}


class SlidesReportMappingTests(unittest.TestCase):
    def test_chart_upload_retries_broken_pipe_then_succeeds(self):
        upload_request = Mock()
        upload_request.execute.side_effect = [
            BrokenPipeError(32, "Broken pipe"),
            {"id": "chart-file-id"},
        ]
        permission_request = Mock()
        permission_request.execute.return_value = {"id": "permission-id"}

        drive_service = Mock()
        drive_service.files.return_value.create.return_value = upload_request
        drive_service.permissions.return_value.create.return_value = (
            permission_request
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            chart_path = Path(temp_dir) / "chart.png"
            chart_path.write_bytes(b"chart")
            with patch("dashboard.slides_report.time.sleep") as sleep:
                mapping, uploaded_ids = upload_chart_images(
                    drive_service,
                    {"{{IG_AUDIENCE_AND_GROWTH}}": chart_path},
                )

        self.assertEqual(upload_request.execute.call_count, 2)
        sleep.assert_called_once_with(1.0)
        self.assertEqual(uploaded_ids, ["chart-file-id"])
        self.assertEqual(
            mapping["{{IG_AUDIENCE_AND_GROWTH}}"],
            "https://drive.google.com/uc?export=download&id=chart-file-id",
        )

    def test_chart_upload_tracks_file_before_permission_failure(self):
        upload_request = Mock()
        upload_request.execute.return_value = {"id": "orphan-file-id"}
        permission_request = Mock()
        permission_request.execute.side_effect = BrokenPipeError(
            32,
            "Broken pipe",
        )

        drive_service = Mock()
        drive_service.files.return_value.create.return_value = upload_request
        drive_service.permissions.return_value.create.return_value = (
            permission_request
        )
        uploaded_ids = []

        with tempfile.TemporaryDirectory() as temp_dir:
            chart_path = Path(temp_dir) / "chart.png"
            chart_path.write_bytes(b"chart")
            with (
                patch("dashboard.slides_report.time.sleep"),
                self.assertRaises(BrokenPipeError),
            ):
                upload_chart_images(
                    drive_service,
                    {"{{IG_AUDIENCE_AND_GROWTH}}": chart_path},
                    uploaded_file_ids=uploaded_ids,
                )

        self.assertEqual(permission_request.execute.call_count, 4)
        self.assertEqual(uploaded_ids, ["orphan-file-id"])

    def test_story_replies_are_imported_as_comments_with_numeric_types_normalized(self):
        post = post_json(
            {
                "Post-ID": "story-1",
                "Number of Likes": Decimal("2"),
                "Story replies": "3",
                "Story shares": "1",
                "Story views": "250",
                "Story reach": "200",
            },
            "story",
            "instagram",
        )

        self.assertEqual(post["comments"], 3.0)
        self.assertEqual(post["total_engagement"], 6.0)

    def test_chart_placeholders_are_image_placeholders(self):
        self.assertTrue(
            is_image_placeholder_key("{{OVERVIEW_AUDIENCE_GROWTH}}")
        )
        self.assertTrue(
            is_image_placeholder_key("{{IG_ENGAGEMENT_BREAKDOWN}}")
        )
        self.assertEqual(SLIDES_IMAGE_REPLACE_METHOD, "CENTER_INSIDE")

    def test_chart_and_story_images_are_prioritized(self):
        self.assertLess(
            image_placeholder_priority("{{IG_AUDIENCE_AND_GROWTH}}"),
            image_placeholder_priority("{{IG_STORY_1_IMAGE}}"),
        )
        self.assertLess(
            image_placeholder_priority("{{IG_STORY_1_IMAGE}}"),
            image_placeholder_priority("{{TK_POST_TOP_1_IMAGE}}"),
        )

    def test_chart_placeholder_is_preserved_for_image_replacement(self):
        slides_service = FakeSlidesService()
        chart_key = "{{IG_AUDIENCE_AND_GROWTH}}"

        audit = replace_text_placeholders_chunked(
            slides_service,
            "presentation-id",
            {
                chart_key: "-",
                "{{IG_TOTAL_FOLLOWERS}}": "1,000",
            },
            skip_image_placeholders={chart_key},
        )

        self.assertEqual(audit["sent_keys"], ["{{IG_TOTAL_FOLLOWERS}}"])
        self.assertEqual(audit["skipped_image_placeholders"], [chart_key])
        self.assertEqual(len(slides_service.batches), 1)

    def test_competitor_metrics_highest_and_lowest_are_colored(self):
        mapping = {
            "{{IG_TOTAL_FOLLOWERS}}": "1,000",
            "{{IG_COMP_1_FOL}}": "2,000",
            "{{IG_COMP_2_FOL}}": "500",
            "{{IG_COMP_3_FOL}}": "-",
            "{{IG_AVG_ER}}": "2.00%",
            "{{IG_COMP_1_ER}}": "1.00%",
            "{{IG_COMP_2_ER}}": "3.00%",
            "{{IG_COMP_3_ER}}": "-",
        }

        styles = competitor_metric_style_mapping(mapping)

        self.assertNotIn("{{IG_TOTAL_FOLLOWERS}}", styles)
        self.assertEqual(styles["{{IG_COMP_1_FOL}}"], COMPETITOR_HIGH_COLOR)
        self.assertEqual(styles["{{IG_COMP_2_FOL}}"], COMPETITOR_LOW_COLOR)
        self.assertEqual(styles["{{IG_COMP_1_ER}}"], COMPETITOR_LOW_COLOR)
        self.assertEqual(styles["{{IG_COMP_2_ER}}"], COMPETITOR_HIGH_COLOR)
        self.assertNotIn("{{IG_COMP_3_FOL}}", styles)

    def test_instagram_feed_and_story_evidence_are_separate(self):
        payload = {
            "client": {
                "client_name": "Example Client",
                "client_code": "example",
                "has_instagram": True,
                "has_facebook": False,
                "has_tiktok": False,
                "has_youtube": False,
            },
            "period": {
                "period_label": "July 2026",
                "period_start": date(2026, 7, 1),
            },
            "reports": {"instagram": {}},
            "content": {
                "instagram": {
                    "top": [
                        {
                            "published_at": datetime(2026, 7, 9),
                            "caption": "Top post",
                        }
                    ],
                    "low": [],
                }
            },
            "all_content": {
                "instagram": [
                    {
                        "published_at": datetime(2026, 7, 2),
                        "caption": "Feed post",
                        "content_type": "reel",
                        "image_url": "https://example.com/feed.jpg",
                        "reach": 875,
                        "likes": 64,
                        "comments": 7,
                        "engagement_rate": 2.4,
                    },
                    {
                        "published_at": datetime(2026, 7, 3),
                        "caption": "-",
                        "content_type": "story",
                        "permalink": "https://instagram.com/stories/example/1",
                        "image_url": "https://example.com/story.jpg",
                        "reach": 420,
                        "views": 510,
                        "comments": 3,
                    },
                ]
            },
            "competitors": {"instagram": []},
            "competitor_content": {"instagram": []},
            "kpi_results": {"instagram": []},
            "trends": {"instagram": []},
            "insights": [
                {
                    "platform": "instagram",
                    "insight_key": "kpi_analysis",
                    "insight_text": "KPI analysis from agent.",
                }
            ],
        }

        mapping = build_mapping(payload)

        self.assertEqual(
            mapping["{{IG_KPI_ANALYSIS}}"],
            "KPI analysis from agent.",
        )
        self.assertEqual(
            mapping["{{IG_POST_TOP_1_DATE}}"],
            "09 JULY 2026",
        )
        self.assertEqual(
            mapping["{{IG_EVIDENCE_1_IMAGE}}"],
            "https://example.com/feed.jpg",
        )
        self.assertEqual(
            mapping["{{IG_STORY_1_IMAGE}}"],
            "https://example.com/story.jpg",
        )
        self.assertEqual(mapping["{{IG_EVIDENCE_1_REACH}}"], "875")
        self.assertEqual(mapping["{{IG_EVIDENCE_1_LIKES}}"], "64")
        self.assertEqual(mapping["{{IG_EVIDENCE_1_COMMENTS}}"], "7")
        self.assertEqual(mapping["{{IG_STORY_1_REACH}}"], "420")
        self.assertEqual(mapping["{{IG_STORY_1_VIEWS}}"], "510")
        self.assertEqual(mapping["{{IG_STORY_1_COMMENTS}}"], "3")
        self.assertEqual(mapping["{{IG_STORY_1_VISITS}}"], "-")
        self.assertNotEqual(
            mapping["{{IG_EVIDENCE_1_IMAGE}}"],
            mapping["{{IG_STORY_1_IMAGE}}"],
        )


if __name__ == "__main__":
    unittest.main()
