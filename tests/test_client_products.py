from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import main


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
            response = self.client.post("/api/clients/client-1/products/meta_ads")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["product"], "meta_ads")
        repository.activate_client_product.assert_called_once_with(
            "client-1", "meta_ads"
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
