from __future__ import annotations

import io
import unittest
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from dashboard import main
from dashboard.services.meta_ads_csv import (
    MetaAdsValidationError,
    derived_metrics,
    parse_meta_ads_csv,
)
from dashboard.services.meta_ads_import import (
    MetaAdsImportService,
    build_import_diagnostics,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "data_example" / "ads_bourbon"


class Upload:
    def __init__(self, path: Path):
        self.filename = path.name
        self.file = path.open("rb")

    def close(self):
        self.file.close()


def fixture_paths() -> dict[str, Path]:
    paths = {}
    for path in FIXTURE_DIR.glob("*.csv"):
        upload = Upload(path)
        try:
            parsed = parse_meta_ads_csv(upload)
            paths[parsed.file_type] = path
        finally:
            upload.close()
    if set(paths) != {"campaign", "adset", "ad", "placement", "demographic", "region"}:
        raise AssertionError("The six Bourbon Meta Ads fixtures are required for this test.")
    return paths


def load_parsed_files():
    parsed = {}
    for file_type, path in fixture_paths().items():
        upload = Upload(path)
        try:
            parsed[file_type] = parse_meta_ads_csv(upload, expected_type=file_type)
        finally:
            upload.close()
    return parsed


class SnapshotRepository:
    def __init__(self):
        self.snapshots = {}
        self.calls = 0

    def import_snapshot(self, **kwargs):
        self.calls += 1
        key = (kwargs["client_id"], kwargs["period_start"], kwargs["period_end"])
        self.snapshots[key] = {
            file_type: {row["source_row_key"] for row in parsed.rows}
            for file_type, parsed in kwargs["files"].items()
        }
        return {
            "import_id": uuid4(),
            "meta_ads_report_period_id": uuid4(),
            "counts": {
                file_type: len(rows) for file_type, rows in self.snapshots[key].items()
            },
        }


class MetaAdsCsvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = fixture_paths()
        cls.parsed = load_parsed_files()

    def uploads(self):
        return {file_type: Upload(path) for file_type, path in self.paths.items()}

    def test_summary_row_is_ignored_for_every_file(self):
        self.assertEqual(
            {name: len(item.rows) for name, item in self.parsed.items()},
            {
                "campaign": 5,
                "adset": 5,
                "ad": 23,
                "placement": 189,
                "demographic": 330,
                "region": 655,
            },
        )
        self.assertTrue(all(item.summary_row is not None for item in self.parsed.values()))
        self.assertTrue(
            all(item.summary_row["source_row_number"] == 2 for item in self.parsed.values())
        )

    def test_campaign_adset_and_ad_rows_map_indonesian_headers(self):
        campaign = self.parsed["campaign"].rows[0]
        self.assertEqual(campaign["campaign_name"], "Bourbon_Reach_2,400,000")
        self.assertEqual(campaign["spend"], Decimal("536016"))
        self.assertEqual(campaign["result_type"], "reach")

        adset = self.parsed["adset"].rows[0]
        self.assertEqual(adset["adset_name"], "Micro Targeting A+")
        self.assertEqual(adset["start_date"].isoformat(), "2026-06-19")

        ad = self.parsed["ad"].rows[0]
        self.assertEqual(ad["ad_name"], "Momen Proper")
        self.assertEqual(ad["adset_name"], "Micro Targeting A+")
        self.assertEqual(ad["quality_ranking"], "Di atas rata-rata")

    def test_breakdown_dimensions_are_retained_verbatim(self):
        self.assertTrue(
            any(
                row["publisher_platform"] == "WhatsApp"
                and row["placement"] == "Status"
                and row["device_platform"] == "Di aplikasi"
                for row in self.parsed["placement"].rows
            )
        )
        demographic = self.parsed["demographic"].rows
        self.assertTrue({row["age"] for row in demographic} >= {"18-24", "65+", "Unknown"})
        self.assertEqual({row["gender"] for row in demographic}, {"female", "male", "unknown"})
        regions = {row["region"] for row in self.parsed["region"].rows}
        self.assertIn("Unknown", regions)
        self.assertIn("Jakarta", regions)

    def test_null_metrics_do_not_crash_and_zero_is_not_null(self):
        ads = self.parsed["ad"].rows
        null_metric = next(
            row for row in ads if row["ad_name"] == "Child Dulu" and row["result_value"] is None
        )
        zero_metric = next(
            row
            for row in ads
            if row["ad_name"] == "Child Dulu" and row["result_value"] == Decimal("0")
        )
        self.assertIsNone(null_metric["link_clicks"])
        self.assertEqual(zero_metric["spend"], Decimal("0"))
        self.assertEqual(zero_metric["impressions"], Decimal("0"))

    def test_wrong_file_type_has_a_useful_error(self):
        upload = Upload(self.paths["region"])
        try:
            with self.assertRaisesRegex(
                MetaAdsValidationError,
                "expected Ads Placement CSV but detected Ads Region CSV",
            ):
                parse_meta_ads_csv(upload, expected_type="placement")
        finally:
            upload.close()

    def test_source_row_keys_are_deterministic_and_preserve_repeated_names(self):
        first_upload = Upload(self.paths["ad"])
        second_upload = Upload(self.paths["ad"])
        try:
            first = parse_meta_ads_csv(first_upload, expected_type="ad")
            second = parse_meta_ads_csv(second_upload, expected_type="ad")
        finally:
            first_upload.close()
            second_upload.close()
        self.assertEqual(
            [row["source_row_key"] for row in first.rows],
            [row["source_row_key"] for row in second.rows],
        )
        self.assertEqual(len({row["source_row_key"] for row in first.rows}), 23)
        repeated = [
            row
            for row in first.rows
            if row["adset_name"] == "Micro Targeting A+" and row["ad_name"] == "Aldi Taher"
        ]
        self.assertEqual(len(repeated), 3)

    def test_diagnostics_use_campaign_once_and_do_not_double_count(self):
        diagnostics, warnings = build_import_diagnostics(self.parsed)
        totals = diagnostics["canonical_totals"]
        self.assertEqual(totals["spend"], Decimal("5425798"))
        self.assertEqual(totals["impressions"], Decimal("2404070"))
        self.assertEqual(totals["reach"], Decimal("1513909"))
        self.assertEqual(totals["source"], "campaign")
        self.assertTrue(all(check["status"] == "passed" for check in diagnostics["checks"]))
        self.assertFalse(diagnostics["relationships"]["reliable"])
        self.assertTrue(any("External Meta entity IDs" in warning for warning in warnings))

    def test_derived_metrics_are_null_safe(self):
        metrics = derived_metrics(
            {
                "spend": Decimal("100"),
                "impressions": Decimal("0"),
                "reach": None,
                "post_engagements": Decimal("0"),
                "link_clicks": Decimal("4"),
            }
        )
        self.assertIsNone(metrics["engagement_rate"])
        self.assertIsNone(metrics["cost_per_engagement"])
        self.assertIsNone(metrics["cost_per_reach"])
        self.assertIsNone(metrics["cpm"])
        self.assertEqual(metrics["cpc"], Decimal("25"))

    def test_duplicate_import_replaces_period_snapshot_without_duplicates(self):
        repository = SnapshotRepository()
        service = MetaAdsImportService(repository)
        payload = {"client_id": str(uuid4())}
        first_uploads = self.uploads()
        second_uploads = self.uploads()
        try:
            first = service.import_files(payload, first_uploads)
            second = service.import_files(payload, second_uploads)
        finally:
            for upload in [*first_uploads.values(), *second_uploads.values()]:
                upload.close()
        self.assertEqual(repository.calls, 2)
        self.assertEqual(len(repository.snapshots), 1)
        self.assertEqual(first["counts"], second["counts"])
        self.assertEqual(first["counts"]["region"], 655)

    def test_all_six_files_are_required(self):
        service = MetaAdsImportService(SnapshotRepository())
        with self.assertRaisesRegex(
            MetaAdsValidationError,
            "All six Meta Ads CSV files are required",
        ):
            service.import_files({"client_id": str(uuid4())}, {})

    def test_inconsistent_reporting_period_is_rejected(self):
        campaign_csv = (
            "Awal pelaporan,Akhir pelaporan,Nama kampanye,Jumlah yang dibelanjakan (IDR),Impresi\n"
            "2026-07-01,2026-07-31,,10,20\n"
            "2026-08-01,2026-08-31,Campaign A,10,20\n"
        ).encode()
        upload = type(
            "MemoryUpload",
            (),
            {"filename": "campaign.csv", "file": io.BytesIO(campaign_csv)},
        )()
        with self.assertRaisesRegex(MetaAdsValidationError, "inconsistent reporting periods"):
            parse_meta_ads_csv(upload, expected_type="campaign")


class MetaAdsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        cls.paths = fixture_paths()

    def test_wrong_file_in_placement_slot_returns_http_400(self):
        paths = dict(self.paths)
        paths["placement"] = paths["region"]
        files = {
            file_type: (path.name, path.read_bytes(), "text/csv")
            for file_type, path in paths.items()
        }
        response = self.client.post(
            "/api/ads/imports",
            data={"client_id": str(uuid4())},
            files=files,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "expected Ads Placement CSV but detected Ads Region CSV",
            response.json()["error"],
        )


if __name__ == "__main__":
    unittest.main()
