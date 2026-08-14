from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.dashboard_repository import post_json
from dashboard.slides_report import (
    COMPETITOR_HIGH_COLOR,
    COMPETITOR_LOW_COLOR,
    SLIDES_IMAGE_REPLACE_METHOD,
    add_evidence_posts,
    build_mapping,
    competitor_metric_style_mapping,
    delete_unused_evidence_slides,
    download_and_normalize_image_files,
    evidence_slide_pruning_plan,
    image_placeholder_priority,
    is_image_placeholder_key,
    merge_image_replacement_audits,
    overview_table_pruning_plan,
    platform_section_pruning_plan,
    replace_image_placeholders_safe,
    resolve_report_presentation,
    replace_text_placeholders_chunked,
    should_replace_images,
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
    def test_image_replacement_is_always_enabled(self):
        with patch.dict(
            "os.environ",
            {"SLIDES_REPLACE_IMAGES": "false"},
        ):
            self.assertTrue(should_replace_images())

    @staticmethod
    def text_element(value):
        return {
            "text": {
                "textElements": [
                    {"textRun": {"content": f"{value}\n"}},
                ]
            }
        }

    @classmethod
    def heading_slide(cls, object_id, heading):
        return {
            "objectId": object_id,
            "pageElements": [
                {
                    "objectId": f"{object_id}-title",
                    "shape": cls.text_element(heading),
                }
            ],
        }

    @staticmethod
    def evidence_slide(object_id: str, *placeholder_keys: str) -> dict:
        return {
            "objectId": object_id,
            "pageElements": [
                {
                    "objectId": f"{object_id}-shape",
                    "shape": {
                        "text": {
                            "textElements": [
                                {
                                    "textRun": {
                                        "content": "\n".join(placeholder_keys)
                                    }
                                }
                            ]
                        }
                    },
                }
            ],
        }

    @patch("dashboard.slides_report.copy_template")
    def test_existing_presentation_is_resumed_without_copy(self, copy_template):
        callback = Mock()

        presentation_id, created = resolve_report_presentation(
            Mock(),
            "template-1",
            "Report 1",
            existing_presentation_id="presentation-existing",
            on_presentation_created=callback,
        )

        self.assertEqual(presentation_id, "presentation-existing")
        self.assertFalse(created)
        copy_template.assert_not_called()
        callback.assert_not_called()

    @patch(
        "dashboard.slides_report.copy_template",
        return_value="presentation-new",
    )
    def test_new_presentation_is_checkpointed_immediately(
        self,
        copy_template,
    ):
        callback = Mock()

        presentation_id, created = resolve_report_presentation(
            Mock(),
            "template-1",
            "Report 1",
            on_presentation_created=callback,
        )

        self.assertEqual(presentation_id, "presentation-new")
        self.assertTrue(created)
        copy_template.assert_called_once()
        callback.assert_called_once_with(
            {
                "presentation_id": "presentation-new",
                "presentation_url": (
                    "https://docs.google.com/presentation/d/"
                    "presentation-new/edit"
                ),
                "report_name": "Report 1",
            }
        )

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

    def test_story_total_interaction_is_imported_as_total_engagement(self):
        post = post_json(
            {
                "Post-ID": "story-1",
                "Number of Likes": Decimal("2"),
                "Reactions, Comments & Shares": "0",
                "Story replies": "3",
                "Story shares": "1",
                "Story total interaction": "12",
                "Story views": "250",
                "Story reach": "200",
                "Profile visits based on the story": "17",
            },
            "story",
            "instagram",
        )

        self.assertEqual(post["comments"], 3.0)
        self.assertEqual(post["profile_visits"], 17)
        self.assertEqual(post["total_engagement"], 12.0)

    def test_story_engagement_falls_back_to_components_for_legacy_csv(self):
        post = post_json(
            {
                "Post-ID": "story-legacy",
                "Number of Likes": Decimal("2"),
                "Story replies": "3",
                "Story shares": "1",
            },
            "story",
            "instagram",
        )

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

    @patch("dashboard.slides_report.execute_slides_batch_update")
    @patch("dashboard.slides_report.validate_image_urls")
    def test_all_images_are_processed_beyond_previous_twenty_call_budget(
        self,
        validate_urls,
        batch_update,
    ):
        image_mapping = {
            f"{{{{FB_EVIDENCE_{index}_IMAGE}}}}": (
                f"https://example.com/{index}.jpg"
            )
            for index in range(1, 46)
        }
        validate_urls.return_value = {
            url: (True, "ok")
            for url in image_mapping.values()
        }
        presentation = {
            "slides": [
                {
                    "objectId": "evidence",
                    "pageElements": [
                        {
                            "objectId": f"image-{index}",
                            "title": placeholder_key,
                            "image": {},
                        }
                        for index, placeholder_key in enumerate(
                            image_mapping,
                            start=1,
                        )
                    ],
                }
            ]
        }
        slides_service = Mock()
        (
            slides_service.presentations.return_value
            .get.return_value.execute.return_value
        ) = presentation
        batch_update.return_value = {"replies": []}

        audit = replace_image_placeholders_safe(
            slides_service,
            "presentation-id",
            image_mapping,
        )

        self.assertEqual(len(audit["replaced"]), 45)
        self.assertEqual(audit["failed"], [])
        self.assertEqual(audit["image_api_calls"], 3)
        self.assertEqual(batch_update.call_count, 3)

    @patch("dashboard.slides_report.http_requests.get")
    def test_proxy_download_normalizes_accessible_image_to_png(self, get):
        source = BytesIO()
        Image.new("RGB", (32, 24), (10, 20, 30)).save(
            source,
            format="WEBP",
        )
        response = MagicMock()
        response.status_code = 200
        response.iter_content.return_value = [source.getvalue()]
        response.__enter__.return_value = response
        get.return_value = response

        with tempfile.TemporaryDirectory() as temp_dir:
            files, failed = download_and_normalize_image_files(
                {"{{IG_POST_COMP_1_IMAGE}}": "https://example.com/image.webp"},
                Path(temp_dir),
            )
            output_path = files["{{IG_POST_COMP_1_IMAGE}}"]
            with Image.open(output_path) as normalized:
                self.assertEqual(normalized.format, "PNG")
                self.assertEqual(normalized.size, (32, 24))

        self.assertEqual(failed, [])

    def test_proxy_success_removes_original_image_failure_from_audit(self):
        merged = merge_image_replacement_audits(
            {
                "attempted": 2,
                "replaced": ["{{IMAGE_OK}}"],
                "failed": [
                    {
                        "placeholder": "{{IMAGE_PROXY}}",
                        "method": "replaceImage",
                        "reason": "Google could not retrieve the image",
                    }
                ],
                "unmatched": [],
                "skipped_non_template": [],
                "object_api_calls": 1,
                "image_api_calls": 1,
            },
            {
                "attempted": 1,
                "replaced": ["{{IMAGE_PROXY}}"],
                "failed": [],
                "unmatched": [],
                "skipped_non_template": [],
                "object_api_calls": 1,
                "image_api_calls": 1,
            },
        )

        self.assertEqual(
            merged["replaced"],
            ["{{IMAGE_OK}}", "{{IMAGE_PROXY}}"],
        )
        self.assertEqual(merged["failed"], [])
        self.assertEqual(merged["proxy_replaced"], ["{{IMAGE_PROXY}}"])
        self.assertEqual(merged["image_api_calls"], 2)

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
                        "profile_visits": 19,
                        "total_engagement": 11,
                    },
                    {
                        "published_at": datetime(2026, 7, 4),
                        "caption": "-",
                        "content_type": "story",
                        "permalink": "https://instagram.com/stories/example/2",
                        "image_url": "https://example.com/story-interactions.jpg",
                        "reach": 600,
                        "views": 720,
                        "comments": 2,
                        "profile_visits": 4,
                        "total_engagement": 25,
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
        self.assertEqual(mapping["{{IG_STORY_1_INTERACTIONS}}"], "11")
        self.assertEqual(mapping["{{IG_STORY_1_VISITS}}"], "19")
        self.assertEqual(mapping["{{IG_STORY_INT_REACH}}"], "600")
        self.assertEqual(mapping["{{IG_STORY_INT_VIEWS}}"], "720")
        self.assertEqual(mapping["{{IG_STORY_INT_INTERACTIONS}}"], "25")
        self.assertEqual(mapping["{{IG_STORY_INT_VISITS}}"], "4")
        self.assertEqual(mapping["{{IG_STORY_INT_DATE}}"], "04 JULY 2026")
        self.assertEqual(
            mapping["{{IG_STORY_INT_IMAGE}}"],
            "https://example.com/story-interactions.jpg",
        )
        self.assertEqual(mapping["{{IG_STORY_PV_REACH}}"], "420")
        self.assertEqual(mapping["{{IG_STORY_PV_VIEWS}}"], "510")
        self.assertEqual(mapping["{{IG_STORY_PV_INTERACTIONS}}"], "11")
        self.assertEqual(mapping["{{IG_STORY_PV_VISITS}}"], "19")
        self.assertEqual(
            mapping["{{IG_STORY_PV_IMAGE}}"],
            "https://example.com/story.jpg",
        )
        self.assertNotEqual(
            mapping["{{IG_EVIDENCE_1_IMAGE}}"],
            mapping["{{IG_STORY_1_IMAGE}}"],
        )

    def test_youtube_evidence_uses_view_value_and_new_placeholder_name(self):
        mapping = {}

        add_evidence_posts(
            mapping,
            "YT",
            [
                {
                    "caption": "YouTube video",
                    "views": 1250,
                    "reach": 800,
                }
            ],
            limit=2,
        )

        self.assertEqual(mapping["{{YT_1_EVIDENCE_VIEW}}"], "1,250")
        self.assertEqual(mapping["{{YT_EVIDENCE_1_VIEW}}"], "1,250")
        self.assertEqual(mapping["{{YT_EVIDENCE_1_REACH}}"], "1,250")
        self.assertEqual(mapping["{{YT_EVIDENCE_2_VIEW}}"], "-")
        self.assertEqual(mapping["{{YT_2_EVIDENCE_VIEW}}"], "-")

    def test_unused_evidence_slides_are_planned_from_template_placeholders(self):
        presentation = {
            "slides": [
                self.evidence_slide(
                    "ig-feed-1",
                    "{{IG_EVIDENCE_1_IMAGE}}",
                    "{{IG_EVIDENCE_4_TITLE}}",
                ),
                self.evidence_slide(
                    "ig-feed-2",
                    "{{IG_EVIDENCE_5_IMAGE}}",
                    "{{IG_EVIDENCE_8_TITLE}}",
                ),
                self.evidence_slide(
                    "ig-feed-3",
                    "{{IG_EVIDENCE_9_IMAGE}}",
                    "{{IG_EVIDENCE_12_TITLE}}",
                ),
                self.evidence_slide(
                    "ig-feed-4",
                    "{{IG_EVIDENCE_13_IMAGE}}",
                    "{{IG_EVIDENCE_16_TITLE}}",
                ),
                self.evidence_slide(
                    "ig-story-1",
                    "{{IG_STORY_1_IMAGE}}",
                    "{{IG_STORY_4_VIEWS}}",
                ),
                self.evidence_slide(
                    "ig-story-2",
                    "{{IG_STORY_5_IMAGE}}",
                    "{{IG_STORY_8_VIEWS}}",
                ),
                {
                    "objectId": "summary",
                    "pageElements": [],
                },
            ]
        }
        payload = {
            "all_content": {
                "instagram": [
                    {
                        "content_type": "reel",
                        "caption": f"Feed {index}",
                    }
                    for index in range(10)
                ]
            }
        }

        plan = evidence_slide_pruning_plan(presentation, payload)

        self.assertEqual(plan["evidence_slide_count"], 6)
        self.assertEqual(plan["kept_slide_count"], 3)
        self.assertEqual(
            plan["deleted_slide_object_ids"],
            ["ig-feed-4", "ig-story-1", "ig-story-2"],
        )
        self.assertEqual(plan["groups"]["IG_EVIDENCE"]["post_count"], 10)
        self.assertEqual(plan["groups"]["IG_EVIDENCE"]["kept_slide_count"], 3)
        self.assertEqual(plan["groups"]["IG_STORY"]["post_count"], 0)
        self.assertEqual(plan["groups"]["IG_STORY"]["kept_slide_count"], 0)

    @patch("dashboard.slides_report.execute_slides_batch_update")
    def test_unused_evidence_slides_are_deleted_in_one_batch(self, batch_update):
        presentation = {
            "slides": [
                self.evidence_slide(
                    "fb-evidence-1",
                    "{{FB_EVIDENCE_1_IMAGE}}",
                    "{{FB_EVIDENCE_4_TITLE}}",
                ),
                self.evidence_slide(
                    "fb-evidence-2",
                    "{{FB_EVIDENCE_5_IMAGE}}",
                    "{{FB_EVIDENCE_8_TITLE}}",
                ),
            ]
        }
        slides_service = Mock()
        (
            slides_service.presentations.return_value
            .get.return_value.execute.return_value
        ) = presentation

        audit, active_placeholders = delete_unused_evidence_slides(
            slides_service,
            "presentation-id",
            {
                "all_content": {
                    "facebook": [
                        {"caption": f"Post {index}"}
                        for index in range(4)
                    ]
                }
            },
        )

        self.assertEqual(audit["deleted_slide_count"], 1)
        self.assertIn("{{FB_EVIDENCE_1_IMAGE}}", active_placeholders)
        self.assertNotIn("{{FB_EVIDENCE_5_IMAGE}}", active_placeholders)
        batch_update.assert_called_once_with(
            slides_service,
            "presentation-id",
            [{"deleteObject": {"objectId": "fb-evidence-2"}}],
        )

    def test_linkedin_report_and_evidence_are_mapped(self):
        payload = {
            "client": {
                "client_name": "Example Client",
                "client_code": "example",
                "has_linkedin": True,
            },
            "period": {
                "period_label": "July 2026",
                "period_start": date(2026, 7, 1),
            },
            "reports": {
                "linkedin": {
                    "total_followers": 2691,
                    "follower_growth": 36,
                    "total_engagement": 42,
                    "reach": 1468,
                    "total_posts": 3,
                    "photo_posts": 3,
                    "video_posts": 0,
                }
            },
            "content": {"linkedin": {"top": [], "low": []}},
            "all_content": {
                "linkedin": [
                    {
                        "caption": "LinkedIn post",
                        "content_type": "photo",
                        "image_url": "https://example.com/linkedin.jpg",
                        "reach": 302,
                        "views": 542,
                        "total_engagement": 10,
                        "shares": 2,
                    }
                ]
            },
            "competitors": {},
            "competitor_content": {},
            "kpi_results": {},
            "trends": {},
            "insights": [],
        }

        mapping = build_mapping(payload)

        self.assertEqual(mapping["{{LK_TOTAL_FOLLOWERS}}"], "2,691")
        self.assertEqual(mapping["{{LK_FOLLOWERS_GROWTH}}"], "36")
        self.assertEqual(mapping["{{LK_TOTAL_PHOTOS}}"], "3")
        self.assertEqual(
            mapping["{{LK_EVIDENCE_1_IMAGE}}"],
            "https://example.com/linkedin.jpg",
        )
        self.assertEqual(mapping["{{LK_EVIDENCE_1_SHARES}}"], "2")

    def test_empty_platform_sections_are_removed_without_deleting_website(self):
        presentation = {
            "slides": [
                self.heading_slide("ig-title", "INSTAGRAM"),
                {"objectId": "ig-content", "pageElements": []},
                self.heading_slide("fb-title", "FACEBOOK"),
                {"objectId": "fb-content", "pageElements": []},
                self.heading_slide("lk-title", "LINKEDIN"),
                {"objectId": "lk-content", "pageElements": []},
                self.heading_slide("th-title", "THREADS"),
                {"objectId": "th-content", "pageElements": []},
                self.heading_slide("website", "WEBSITE TRAFFIC & SEO HEALTH"),
                {"objectId": "website-content", "pageElements": []},
            ]
        }
        payload = {
            "client": {
                "has_instagram": True,
                "has_facebook": True,
                "has_linkedin": True,
                "has_threads": True,
            },
            "reports": {
                "instagram": {"id": "ig-report"},
                "linkedin": {"id": "lk-report"},
            },
        }

        plan = platform_section_pruning_plan(presentation, payload)

        self.assertEqual(plan["active_platforms"], ["instagram", "linkedin"])
        self.assertEqual(plan["deleted_platforms"], ["facebook", "threads"])
        self.assertEqual(
            plan["deleted_slide_object_ids"],
            ["fb-title", "fb-content", "th-title", "th-content"],
        )
        self.assertNotIn("website", plan["deleted_slide_object_ids"])
        self.assertNotIn("website-content", plan["deleted_slide_object_ids"])

    def test_overview_removes_middle_columns_and_resizes_remaining_columns(self):
        headers = [
            "MATRIX",
            "INSTAGRAM",
            "FACEBOOK",
            "TIKTOK",
            "YOUTUBE",
            "LINKEDIN",
            "THREADS",
        ]
        presentation = {
            "slides": [
                {
                    "objectId": "overview-slide",
                    "pageElements": [
                        {
                            "objectId": "overview-table",
                            "size": {
                                "width": {"magnitude": 3000000, "unit": "EMU"}
                            },
                            "table": {
                                "columns": len(headers),
                                "tableRows": [
                                    {
                                        "tableCells": [
                                            self.text_element(header)
                                            for header in headers
                                        ]
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
        payload = {
            "client": {
                "has_instagram": True,
                "has_facebook": True,
                "has_linkedin": True,
            },
            "reports": {
                "instagram": {"id": "ig-report"},
                "facebook": {"id": "fb-report"},
                "linkedin": {"id": "lk-report"},
            },
        }

        plan = overview_table_pruning_plan(presentation, payload)

        self.assertTrue(plan["found"])
        self.assertEqual(plan["deleted_column_indices"], [3, 4, 6])
        self.assertEqual(
            [
                request["deleteTableColumn"]["cellLocation"]["columnIndex"]
                for request in plan["requests"]
                if "deleteTableColumn" in request
            ],
            [6, 4, 3],
        )
        self.assertEqual(plan["remaining_column_count"], 4)
        self.assertEqual(plan["total_table_width"], 10972800)
        self.assertEqual(plan["matrix_column_width"], 1929625)
        self.assertAlmostEqual(plan["target_column_width"], 3014391.6666666665)
        self.assertEqual(
            plan["requests"][-2]["updateTableColumnProperties"]["columnIndices"],
            [0],
        )
        self.assertEqual(
            plan["requests"][-1]["updateTableColumnProperties"]["columnIndices"],
            [1, 2, 3],
        )

    def test_overview_width_is_restored_when_columns_were_already_deleted(self):
        headers = ["MATRIX", "INSTAGRAM", "FACEBOOK", "LINKEDIN"]
        presentation = {
            "slides": [
                {
                    "objectId": "overview-slide",
                    "pageElements": [
                        {
                            "objectId": "overview-table",
                            "table": {
                                "columns": len(headers),
                                "tableRows": [
                                    {
                                        "tableCells": [
                                            self.text_element(header)
                                            for header in headers
                                        ]
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
        payload = {
            "client": {
                "has_instagram": True,
                "has_facebook": True,
                "has_linkedin": True,
            },
            "reports": {
                "instagram": {"id": "ig-report"},
                "facebook": {"id": "fb-report"},
                "linkedin": {"id": "lk-report"},
            },
        }

        plan = overview_table_pruning_plan(presentation, payload)

        self.assertEqual(plan["deleted_column_indices"], [])
        self.assertEqual(len(plan["requests"]), 2)
        self.assertEqual(plan["total_table_width"], 10972800)


if __name__ == "__main__":
    unittest.main()
