from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.repositories.dashboard_repository import (
    content_type_from_row,
    deduplicate_content_rows,
    split_combined_content_rows,
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
                "instagram": 10,
                "facebook": 11,
                "tiktok": 3,
                "youtube": 3,
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


if __name__ == "__main__":
    unittest.main()
