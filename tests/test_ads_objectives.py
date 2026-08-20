import unittest

from dashboard.services.ads_objectives import (
    normalize_metric_keys,
    objective_catalog,
    suggest_meta_objective,
)
from dashboard.repositories.meta_ads_repository import META_GOAL_RESULT_TYPES


class AdsObjectiveCatalogTests(unittest.TestCase):
    def test_catalog_contains_all_configurable_scopes(self):
        catalog = objective_catalog()
        self.assertEqual(set(catalog["scopes"]), {"meta", "google_sem", "google_gdn", "youtube", "tiktok"})
        self.assertEqual(
            [item["key"] for item in catalog["scopes"]["meta"]["objectives"]],
            ["reach", "engagement", "views", "link_clicks", "leads"],
        )

    def test_objective_suggestion_uses_campaign_and_delivery_signals(self):
        self.assertEqual(suggest_meta_objective("OUTCOME_LEADS")["objective"], "leads")
        self.assertEqual(suggest_meta_objective("OUTCOME_ENGAGEMENT", ["THRUPLAY"])["objective"], "views")
        self.assertEqual(suggest_meta_objective("OUTCOME_TRAFFIC", ["LINK_CLICKS"])["objective"], "link_clicks")
        self.assertEqual(suggest_meta_objective("OUTCOME_AWARENESS")["objective"], "reach")

    def test_metric_order_is_preserved_and_empty_is_valid(self):
        self.assertEqual(normalize_metric_keys("meta", "reach", ["spend", "reach", "spend"]), ["spend", "reach"])
        self.assertEqual(normalize_metric_keys("meta", "reach", []), [])

    def test_meta_optional_metrics_can_be_enabled_for_any_objective(self):
        self.assertEqual(
            normalize_metric_keys("meta", "reach", ["reach", "post_comments", "result_rate"]),
            ["reach", "post_comments", "result_rate"],
        )
        catalog = objective_catalog()["scopes"]["meta"]["objectives"]
        reach = next(item for item in catalog if item["key"] == "reach")
        engagement = next(item for item in catalog if item["key"] == "engagement")
        self.assertEqual(reach["metric_keys"], engagement["metric_keys"])
        self.assertNotEqual(reach["default_metric_keys"], engagement["default_metric_keys"])

    def test_metric_outside_objective_catalog_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported metric"):
            normalize_metric_keys("meta", "reach", ["leads"])

    def test_fresh_database_bootstrap_contains_ads_objective_schema(self):
        with open("db/init/001_init.sql", encoding="utf-8") as schema_file:
            sql = schema_file.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS ads_metric_configurations", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS meta_ads_campaign_objective_mappings", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS schema_version", sql)

    def test_platform_detail_supports_canonical_meta_result_types(self):
        self.assertEqual(META_GOAL_RESULT_TYPES["views"], ("video_view",))
        self.assertEqual(META_GOAL_RESULT_TYPES["link_clicks"], ("link_click",))
        self.assertEqual(META_GOAL_RESULT_TYPES["leads"], ("lead",))


if __name__ == "__main__":
    unittest.main()
