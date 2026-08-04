from __future__ import annotations

import csv
import sys
import unittest
from decimal import Decimal
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.dashboard_repository import (
    content_type_from_row,
    deduplicate_content_rows,
    platform_from_content_row,
    split_combined_content_rows,
    summarize_post_objects,
    json_safe,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data_example"
    / "par"
    / "juli"
    / "par_all_content_juli.csv"
)


class UnifiedContentImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with FIXTURE.open("r", encoding="utf-8-sig", newline="") as stream:
            cls.rows = list(csv.DictReader(stream, delimiter=";"))

    def test_combined_file_is_split_by_platform(self):
        split_rows, audit = split_combined_content_rows(self.rows)

        self.assertEqual(
            {platform: len(rows) for platform, rows in split_rows.items()},
            {
                "instagram": 13,
                "facebook": 14,
                "tiktok": 3,
                "youtube": 3,
                "linkedin": 3,
                "threads": 0,
            },
        )
        self.assertEqual(audit["summary_rows_skipped"], 1)
        self.assertEqual(audit["unknown_count"], 0)

    def test_content_types_are_detected(self):
        split_rows, _audit = split_combined_content_rows(self.rows)

        detected = {}
        for platform, rows in split_rows.items():
            fallback = "video" if platform in {"tiktok", "youtube"} else "post"
            detected[platform] = {
                content_type_from_row(row, platform, fallback)
                for row in rows
            }

        self.assertEqual(
            detected["instagram"],
            {"reel", "image", "carousel"},
        )
        self.assertEqual(
            detected["facebook"],
            {"reel", "image", "carousel"},
        )
        self.assertEqual(detected["tiktok"], {"video"})
        self.assertEqual(detected["youtube"], {"short", "video"})

    def test_linkedin_and_threads_are_detected_from_network_or_link(self):
        self.assertEqual(
            platform_from_content_row({"Social network": "LinkedIn"}),
            "linkedin",
        )
        self.assertEqual(
            platform_from_content_row({"Link": "https://www.threads.net/@mai/post/1"}),
            "threads",
        )
        self.assertEqual(
            platform_from_content_row({"Link": "https://www.linkedin.com/posts/mai-1"}),
            "linkedin",
        )

    def test_new_platform_content_types_are_normalized(self):
        self.assertEqual(
            content_type_from_row(
                {"Post type": "Native Video"},
                "linkedin",
                "photo",
            ),
            "video",
        )
        self.assertEqual(
            content_type_from_row({}, "linkedin", "photo"),
            "photo",
        )
        self.assertEqual(
            content_type_from_row(
                {"Number of Image Posts": "1"},
                "threads",
                "text",
            ),
            "photo",
        )
        self.assertEqual(
            content_type_from_row({}, "threads", "text"),
            "text",
        )

    def test_unknown_rows_warn_without_blocking_valid_rows(self):
        rows = [
            self.rows[0],
            {
                "Profile": "Unknown Profile",
                "Post-ID": "unknown-post",
                "Social network": "",
                "Link": "",
                "Profile-ID": "",
            },
        ]
        split_rows, audit = split_combined_content_rows(rows)

        self.assertEqual(sum(map(len, split_rows.values())), 1)
        self.assertEqual(audit["unknown_count"], 1)
        self.assertEqual(audit["unknown_rows"][0]["post_id"], "unknown-post")

    def test_profile_id_fallback_and_deduplication(self):
        row = {
            "Profile": "Profile without network",
            "Post-ID": "same-post",
            "Social network": "",
            "Link": "",
            "Profile-ID": "profile-123",
        }
        split_rows, audit = split_combined_content_rows(
            [row, dict(row)],
            {"profile-123": "instagram"},
        )

        self.assertEqual(len(split_rows["instagram"]), 1)
        self.assertEqual(audit["duplicates_skipped"]["instagram"], 1)
        deduplicated, duplicate_count = deduplicate_content_rows(
            [row, dict(row)],
            "instagram",
            "post",
        )
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(duplicate_count, 1)

    def test_stored_story_rows_can_be_preserved_during_feed_update(self):
        summary = summarize_post_objects(
            [
                {
                    "post_id": "story-1",
                    "content_type": "story",
                    "likes": 0,
                    "comments": 0,
                    "shares": 2,
                    "reach": 100,
                    "views": 120,
                    "total_engagement": 2,
                }
            ],
            "story",
        )

        self.assertEqual(summary["totals"]["count"], 1)
        self.assertEqual(summary["totals"]["reach"], 100)
        self.assertEqual(summary["content_type_counts"], {"story": 1})

    def test_stored_decimal_metrics_can_be_added_to_csv_float_metrics(self):
        stored_feed = summarize_post_objects(
            [
                {
                    "post_id": "feed-1",
                    "content_type": "image",
                    "likes": Decimal("10"),
                    "comments": Decimal("2"),
                    "shares": Decimal("1"),
                    "reach": Decimal("100"),
                    "total_engagement": Decimal("13"),
                }
            ],
            "post",
        )
        csv_story = summarize_post_objects(
            [
                {
                    "post_id": "story-1",
                    "content_type": "story",
                    "shares": 2.0,
                    "reach": 50.0,
                    "total_engagement": 2.0,
                }
            ],
            "story",
        )

        combined_engagement = (
            stored_feed["totals"]["engagement"]
            + csv_story["totals"]["engagement"]
        )
        combined_reach = (
            stored_feed["totals"]["reach"]
            + csv_story["totals"]["reach"]
        )

        self.assertEqual(combined_engagement, 15.0)
        self.assertEqual(combined_reach, 150.0)

    def test_preserved_content_is_json_safe(self):
        serialized = json_safe(
            {
                "published_at": datetime(2026, 7, 1, 12, 30),
                "total_engagement": Decimal("13.5"),
            }
        )

        self.assertEqual(serialized["published_at"], "2026-07-01T12:30:00")
        self.assertEqual(serialized["total_engagement"], 13.5)


if __name__ == "__main__":
    unittest.main()
