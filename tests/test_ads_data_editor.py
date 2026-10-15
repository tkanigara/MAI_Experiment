from test_support import OfflineTestCase
from datetime import date
from pathlib import Path
from dashboard.repositories.meta_ads_repository import MetaAdsRepository


class TestAdsDataEditor(OfflineTestCase):

    def test_ads_editor_numeric_values_are_normalized(self):
        self.assertEqual(MetaAdsRepository._editor_value("reach", "1,234.5"), 1234.5)
        self.assertIs(MetaAdsRepository._editor_value("leads", ""), None)

    def test_ads_editor_rejects_negative_metrics_and_empty_names(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            MetaAdsRepository._editor_value("spend", "-1")
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            MetaAdsRepository._editor_value("campaign_name", " ")

    def test_ads_editor_schema_is_available_for_new_and_existing_databases(self):
        root = Path(__file__).resolve().parents[1]
        migration = (root / "db/migrations/011_ads_data_editor.sql").read_text(
            encoding="utf-8"
        )
        initial_schema = (root / "db/init/001_init.sql").read_text(encoding="utf-8")
        for table in ("meta_ads_data_overrides", "meta_ads_data_edit_history"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", migration)
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", initial_schema)

    def test_meta_sync_range_presets_are_resolved_inside_report_month(self):
        full = MetaAdsRepository.resolve_sync_range(
            date(2026, 7, 1), {"preset": "month_to_date"}
        )
        week = MetaAdsRepository.resolve_sync_range(
            date(2026, 7, 17), {"preset": "last_7_days"}
        )
        custom = MetaAdsRepository.resolve_sync_range(
            date(2026, 7, 1),
            {"preset": "custom", "start": "2026-07-08", "end": "2026-07-14"},
        )
        self.assertEqual(
            (full["start"], full["end"]), (date(2026, 7, 1), date(2026, 7, 31))
        )
        self.assertEqual(
            (week["start"], week["end"]), (date(2026, 7, 25), date(2026, 7, 31))
        )
        self.assertEqual(
            (custom["start"], custom["end"]), (date(2026, 7, 8), date(2026, 7, 14))
        )

    def test_meta_sync_custom_range_cannot_cross_report_month(self):
        with self.assertRaisesRegex(ValueError, "within the selected report month"):
            MetaAdsRepository.resolve_sync_range(
                date(2026, 7, 1),
                {"preset": "custom", "start": "2026-07-25", "end": "2026-08-02"},
            )
