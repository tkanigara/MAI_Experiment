import unittest

from dashboard.services.ads_objectives import (
    calculate_cost_per_result,
    normalize_metric_keys,
    objective_catalog,
    suggest_meta_objective,
)
from dashboard.repositories.meta_ads_repository import (
    META_GOAL_RESULT_TYPES,
    _normalize_entity_targets,
)


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

    def test_cost_per_result_is_per_thousand_for_reach_and_impressions(self):
        self.assertEqual(calculate_cost_per_result(250000, 100000, "reach"), 2500)
        self.assertEqual(calculate_cost_per_result(250000, 100000, "impressions"), 2500)
        self.assertEqual(calculate_cost_per_result(250000, 100000, "leads"), 2.5)

    def test_cost_per_result_is_empty_when_result_is_unavailable(self):
        self.assertIsNone(calculate_cost_per_result(250000, None, "reach"))
        self.assertIsNone(calculate_cost_per_result(250000, 0, "reach"))

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

    def test_ad_targets_are_normalized_without_turning_blanks_into_zero(self):
        rows = _normalize_entity_targets(
            [
                {
                    "ad_id": "ad-1",
                    "ad_name": "Creative A",
                    "adset_id": "set-1",
                    "adset_name": "Audience A",
                    "target": "125",
                    "budget": "250000",
                },
                {"ad_id": "ad-2", "ad_name": "Creative B", "target": "", "budget": ""},
            ],
            "ad_id",
            "ad_name",
            extra_label_fields=("adset_id", "adset_name"),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ad_id"], "ad-1")
        self.assertEqual(rows[0]["target"], 125.0)
        self.assertEqual(rows[0]["budget"], 250000.0)
        self.assertEqual(rows[0]["adset_id"], "set-1")

    def test_entity_targets_reject_negative_values(self):
        with self.assertRaisesRegex(ValueError, "budget must be a non-negative number"):
            _normalize_entity_targets(
                [{"ad_id": "ad-1", "budget": -1}],
                "ad_id",
                "ad_name",
            )


if __name__ == "__main__":
    unittest.main()
