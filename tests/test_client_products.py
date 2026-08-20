from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import main
from dashboard.services.ads_workspace import (
    ads_period_configuration,
    ads_platform_catalog,
    ads_product_configuration,
)


class ClientProductApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_client_list_forwards_product_filter(self):
        repository = Mock()
        repository.clients.return_value = [
            {"id": "client-1", "client_name": "Ads Only", "products": ["meta_ads"]}
        ]

        with patch.object(main, "repository", repository):
            response = self.client.get("/api/clients", params={"product": "meta_ads"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["products"], ["meta_ads"])
        repository.clients.assert_called_once_with("meta_ads")

    def test_product_summary_is_exposed(self):
        repository = Mock()
        repository.client_product_summary.return_value = {
            "social_media": 3,
            "meta_ads": 2,
        }

        with patch.object(main, "repository", repository):
            response = self.client.get("/api/client-products/summary")

        self.assertEqual(
            response.json(),
            {"social_media": 3, "meta_ads": 2},
        )

    def test_existing_client_can_be_enabled_for_ads(self):
        repository = Mock()
        repository.activate_client_product.return_value = {
            "id": "client-1",
            "product": "meta_ads",
        }

        with patch.object(main, "repository", repository):
            response = self.client.post(
                "/api/clients/client-1/products/meta_ads",
                json={"ads_platforms": ["instagram", "facebook", "youtube"]},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["product"], "meta_ads")
        repository.activate_client_product.assert_called_once_with(
            "client-1",
            "meta_ads",
            {"ads_platforms": ["instagram", "facebook", "youtube"]},
        )

    def test_shared_client_can_be_removed_from_one_product(self):
        repository = Mock()
        repository.deactivate_client_product.return_value = {
            "id": "client-1",
            "product": "social_media",
            "is_active": False,
        }

        with patch.object(main, "repository", repository):
            response = self.client.delete(
                "/api/clients/client-1/products/social_media"
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])
        repository.deactivate_client_product.assert_called_once_with(
            "client-1", "social_media"
        )

    def test_ads_periods_use_the_ads_repository(self):
        repository = Mock()
        repository.client_periods.return_value = {
            "client": {"id": "client-1", "client_name": "Bourbon"},
            "periods": [{"id": "ads-period-1"}],
        }

        with patch.object(main, "meta_ads_repository", repository):
            response = self.client.get("/api/ads/clients/client-1/periods")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["periods"][0]["id"], "ads-period-1")
        repository.client_periods.assert_called_once_with("client-1")

    def test_ads_platform_contract_exposes_future_sources_without_tables(self):
        response = self.client.get("/api/ads/platforms")

        self.assertEqual(response.status_code, 200)
        rows = {row["key"]: row for row in response.json()}
        self.assertEqual(set(rows), {"instagram", "facebook", "google_sem", "google_gdn", "youtube", "tiktok"})
        self.assertEqual(rows["instagram"]["ingestion_status"], "available")
        self.assertEqual(rows["facebook"]["source"], "meta")
        self.assertEqual(rows["youtube"]["storage_status"], "not_created")
        self.assertEqual(rows["tiktok"]["ingestion_status"], "coming_soon")
        self.assertEqual(rows["google_sem"]["ingestion_status"], "coming_soon")
        self.assertEqual(rows["google_gdn"]["source"], "google_ads")

    def test_ads_period_can_be_deleted_independently(self):
        repository = Mock()
        repository.delete_period.return_value = {
            "deleted": True,
            "period_id": "period-1",
        }

        with patch.object(main, "meta_ads_repository", repository):
            response = self.client.delete(
                "/api/ads/clients/client-1/periods/period-1"
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        repository.delete_period.assert_called_once_with("client-1", "period-1")

    def test_ads_platform_detail_uses_goal_aware_repository_contract(self):
        repository = Mock()
        repository.platform_detail.return_value = {
            "platform": {"key": "instagram"},
            "data_status": "ready",
            "goals": [{"key": "reach", "metrics": {"result_value": 1000}}],
        }

        with patch.object(main, "meta_ads_repository", repository):
            response = self.client.get(
                "/api/ads/clients/client-1/periods/period-1/platforms/instagram"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["goals"][0]["key"], "reach")
        repository.platform_detail.assert_called_once_with(
            "client-1", "period-1", "instagram"
        )

    def test_ads_period_overview_exposes_kpi_and_budget_rows(self):
        repository = Mock()
        repository.period_overview.return_value = {
            "period_id": "period-1",
            "rows": [{"platform": "instagram", "goal_key": "reach"}],
        }

        with patch.object(main, "meta_ads_repository", repository):
            response = self.client.get(
                "/api/ads/clients/client-1/periods/period-1/overview"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rows"][0]["goal_key"], "reach")
        repository.period_overview.assert_called_once_with("client-1", "period-1")

    def test_ads_period_configuration_can_be_updated_without_reimport(self):
        repository = Mock()
        repository.update_period_configuration.return_value = {
            "period_id": "period-1",
            "goals": {"instagram": [{"key": "reach"}]},
        }
        payload = {
            "ads_goals": {
                "instagram": [{"key": "reach", "target_monthly": 1000}]
            }
        }

        with patch.object(main, "meta_ads_repository", repository):
            response = self.client.put(
                "/api/ads/clients/client-1/periods/period-1/configuration",
                json=payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["goals"]["instagram"][0]["key"], "reach")
        repository.update_period_configuration.assert_called_once_with(
            "client-1", "period-1", payload
        )


class AdsWorkspaceContractTests(unittest.TestCase):
    def test_platform_configuration_is_ordered_and_validated(self):
        configuration = ads_product_configuration(
            ["tiktok", "instagram", "youtube"]
        )
        self.assertEqual(
            configuration["platforms"],
            ["instagram", "youtube", "tiktok"],
        )
        self.assertEqual(set(configuration), {"platforms"})
        with self.assertRaisesRegex(ValueError, "Unsupported Ads platforms"):
            ads_product_configuration(["linkedin"])

    def test_goal_configuration_supports_month_specific_subset_and_targets(self):
        configuration = ads_period_configuration({
            "ads_goals": {
                "instagram": [
                    {"key": "reach", "target_monthly": "1000000", "budget_monthly": 4000000},
                    {"key": "engagement", "target_monthly": 30000},
                ],
                "facebook": [{"key": "page_likes", "target_cost_per_result": 10000}],
            },
        }, ["instagram", "facebook"])

        self.assertEqual(
            [goal["key"] for goal in configuration["goals"]["instagram"]],
            ["reach", "engagement"],
        )
        self.assertEqual(
            configuration["goals"]["instagram"][0]["target_monthly"],
            1000000,
        )
        self.assertEqual(
            configuration["goals"]["facebook"][0]["key"],
            "page_likes",
        )

    def test_a_month_can_skip_a_connected_platform(self):
        configuration = ads_period_configuration({
            "ads_goals": {
                "instagram": [],
                "facebook": [{"key": "reach"}],
            }
        }, ["instagram", "facebook"])
        self.assertEqual(configuration["goals"]["instagram"], [])
        self.assertEqual(configuration["goals"]["facebook"][0]["key"], "reach")

    def test_a_month_requires_at_least_one_goal_overall(self):
        with self.assertRaisesRegex(ValueError, "at least one Ads goal"):
            ads_period_configuration({
                "ads_goals": {"instagram": []},
            }, ["instagram"])

    def test_native_goals_are_exposed_in_platform_catalog(self):
        rows = {row["key"]: row for row in ads_platform_catalog()}
        self.assertEqual(
            [goal["key"] for goal in rows["facebook"]["goals"]],
            ["reach", "engagement", "views", "link_clicks", "leads", "page_likes"],
        )
        self.assertEqual(
            [goal["key"] for goal in rows["youtube"]["goals"]],
            ["video_views"],
        )

    def test_catalog_marks_unconfigured_platforms(self):
        rows = {
            row["key"]: row
            for row in ads_platform_catalog(["instagram", "facebook"])
        }
        self.assertTrue(rows["instagram"]["configured"])
        self.assertFalse(rows["youtube"]["configured"])

    def test_catalog_marks_goals_active_for_the_selected_month(self):
        rows = {
            row["key"]: row
            for row in ads_platform_catalog(
                ["instagram", "facebook"],
                {"ads_goals": {"instagram": [{"key": "reach"}], "facebook": []}},
            )
        }
        self.assertEqual([goal["key"] for goal in rows["instagram"]["active_goals"]], ["reach"])
        self.assertEqual(rows["facebook"]["active_goals"], [])


class ClientProductSchemaTests(unittest.TestCase):
    def test_ads_periods_do_not_reference_social_periods_or_etl_runs(self):
        sql = (
            Path(__file__).resolve().parents[1]
            / "db"
            / "migrations"
            / "007_meta_ads.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS client_products", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS meta_ads_report_periods", sql)
        self.assertIn("meta_ads_report_period_id", sql)
        self.assertIn("WHERE NOT EXISTS (SELECT 1 FROM client_products)", sql)
        self.assertNotIn("REFERENCES report_periods(", sql)
        self.assertNotIn("etl_run_id", sql)

        period_goal_sql = (
            Path(__file__).resolve().parents[1]
            / "db"
            / "migrations"
            / "008_ads_period_goals.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN IF NOT EXISTS configuration JSONB", period_goal_sql)


if __name__ == "__main__":
    unittest.main()
