from datetime import date
from pathlib import Path

import pytest

from dashboard.repositories.meta_ads_repository import MetaAdsRepository


def test_ads_editor_numeric_values_are_normalized():
    assert MetaAdsRepository._editor_value("reach", "1,234.5") == 1234.5
    assert MetaAdsRepository._editor_value("leads", "") is None


def test_ads_editor_rejects_negative_metrics_and_empty_names():
    with pytest.raises(ValueError, match="cannot be negative"):
        MetaAdsRepository._editor_value("spend", "-1")
    with pytest.raises(ValueError, match="cannot be empty"):
        MetaAdsRepository._editor_value("campaign_name", " ")


def test_ads_editor_schema_is_available_for_new_and_existing_databases():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "db/migrations/011_ads_data_editor.sql").read_text(encoding="utf-8")
    initial_schema = (root / "db/init/001_init.sql").read_text(encoding="utf-8")
    for table in ("meta_ads_data_overrides", "meta_ads_data_edit_history"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
        assert f"CREATE TABLE IF NOT EXISTS {table}" in initial_schema


def test_meta_sync_range_presets_are_resolved_inside_report_month():
    full = MetaAdsRepository.resolve_sync_range(date(2026, 7, 1), {"preset": "month_to_date"})
    week = MetaAdsRepository.resolve_sync_range(date(2026, 7, 17), {"preset": "last_7_days"})
    custom = MetaAdsRepository.resolve_sync_range(date(2026, 7, 1), {
        "preset": "custom", "start": "2026-07-08", "end": "2026-07-14",
    })
    assert (full["start"], full["end"]) == (date(2026, 7, 1), date(2026, 7, 31))
    assert (week["start"], week["end"]) == (date(2026, 7, 25), date(2026, 7, 31))
    assert (custom["start"], custom["end"]) == (date(2026, 7, 8), date(2026, 7, 14))


def test_meta_sync_custom_range_cannot_cross_report_month():
    with pytest.raises(ValueError, match="within the selected report month"):
        MetaAdsRepository.resolve_sync_range(date(2026, 7, 1), {
            "preset": "custom", "start": "2026-07-25", "end": "2026-08-02",
        })
