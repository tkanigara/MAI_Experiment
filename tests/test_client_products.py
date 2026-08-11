from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import main
from dashboard.services.ads_workspace import (
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
        self.assertEqual(set(rows), {"instagram", "facebook", "youtube", "tiktok"})
        self.assertEqual(rows["instagram"]["ingestion_status"], "available")
        self.assertEqual(rows["facebook"]["source"], "meta")
        self.assertEqual(rows["youtube"]["storage_status"], "not_created")
        self.assertEqual(rows["tiktok"]["ingestion_status"], "coming_soon")

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


class AdsWorkspaceContractTests(unittest.TestCase):
    def test_platform_configuration_is_ordered_and_validated(self):
        self.assertEqual(
            ads_product_configuration(["tiktok", "instagram", "youtube"]),
            {"platforms": ["instagram", "youtube", "tiktok"]},
        )
        with self.assertRaisesRegex(ValueError, "Unsupported Ads platforms"):
            ads_product_configuration(["linkedin"])

    def test_catalog_marks_unconfigured_platforms(self):
        rows = {
            row["key"]: row
            for row in ads_platform_catalog(["instagram", "facebook"])
        }
        self.assertTrue(rows["instagram"]["configured"])
        self.assertFalse(rows["youtube"]["configured"])


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


if __name__ == "__main__":
    unittest.main()
