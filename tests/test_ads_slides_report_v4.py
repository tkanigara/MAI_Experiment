import unittest

from dashboard.ads_slides_report import (
    ARCHETYPE,
    _fill_adset,
    _fill_comparison,
    _fill_overview,
    _slide_plan,
    build_ads_mapping,
)


def payload(objective="leads", platform="instagram"):
    rows = [
        {
            "id": f"ad-{index}",
            "name": f"Creative {index}",
            "campaign_name": "Campaign A",
            "adset_name": "Audience A",
            "thumbnail_url": f"https://example.com/{index}.png",
            "metrics": {
                "result": 10 - index,
                "reach": 1000 * index,
                "impressions": 1500 * index,
                "spend": 100000 * index,
            },
        }
        for index in range(1, 6)
    ]
    return {
        "repo": None,
        "client": {"id": "client-1", "client_name": "Example Client"},
        "period": {"id": "period-1", "period_label": "July 2026", "period_start": "2026-07-01", "period_end": "2026-07-31"},
        "model": "dunlop",
        "platform_scope": platform,
        "objective": objective,
        "analysis": {"data_status": "ready", "summary": {"result": 35, "reach": 15000, "impressions": 22500, "spend": 1500000}},
        "metric_keys": ["result", "reach", "impressions", "spend"],
        "source": {"type": "api", "updated_at": "2026-08-01T12:30:00+00:00"},
        "target": 40,
        "budget": 2000000,
        "actual": 35,
        "spend": 1500000,
        "achievement": 87.5,
        "cumulative": {"target": 80, "budget": 4000000, "actual": 70, "spend": 3000000},
        "rows": rows,
        "breakdown": {
            "placements": [{"label": "instagram_feed", "result": 20, "impressions": 1000}],
            "demographics": [{"label": "25-34 · female", "result": 12, "impressions": 600}],
            "regions": [{"label": "Jakarta", "result": 15, "impressions": 700}],
        },
        "analysis_sections": {},
        "evidence_fingerprint": "test-fingerprint",
        "warning": "",
    }


class AdsSlidesV4Tests(unittest.TestCase):
    def test_mapping_uses_v4_creative_and_three_content_contract(self):
        mapping = build_ads_mapping(payload())
        self.assertEqual(mapping["{{CREATIVE_ROW_1_NAME}}"], "Creative 1")
        self.assertEqual(mapping["{{BEST_CONTENT_3_NAME}}"], "Creative 3")
        self.assertEqual(mapping["{{KPI_1_LABEL}}"], "Primary Result")
        self.assertIn("Creative 1", mapping["{{OPTIMIZATION_WHAT_WORKED}}"])

    def test_dunlop_plan_clones_each_breakdown_and_platform_conclusion(self):
        plans = _slide_plan([payload()], "dunlop")
        sources = [plan["source"] for plan in plans]
        self.assertEqual(sources.count(ARCHETYPE["breakdown"]), 3)
        self.assertEqual(sources.count(ARCHETYPE["content"]), 1)
        self.assertEqual(sources.count(ARCHETYPE["platform_conclusion"]), 1)
        self.assertEqual(plans[-1]["source"], ARCHETYPE["end"])
        self.assertEqual(len({plan["slide_id"] for plan in plans}), len(plans))

    def test_adset_total_uses_parent_grain_for_non_additive_metrics(self):
        current = payload()
        current["metric_keys"] = ["reach", "impressions", "spend", "frequency"]
        mapping = build_ads_mapping(current)
        adset = {
            "name": "Audience A",
            "metrics": {"reach": 4200, "impressions": 22500, "spend": 1500000, "frequency": 5.36},
        }
        _fill_adset(mapping, current, adset)
        self.assertEqual(mapping["{{AD_TOTAL_METRIC_1}}"], "4,200")
        self.assertEqual(mapping["{{AD_TOTAL_METRIC_2}}"], "22,500")
        self.assertEqual(mapping["{{AD_TOTAL_METRIC_3}}"], "Rp 1,500,000")
        self.assertEqual(mapping["{{AD_TOTAL_METRIC_4}}"], "5.36")

    def test_overview_does_not_add_results_with_different_units(self):
        leads = payload("leads")
        reach = payload("reach")
        plans = _slide_plan([leads, reach], "dunlop")
        cumulative = plans[1]["mapping"]
        self.assertEqual(cumulative["{{CUMULATIVE_TOTAL_KPI_LABEL}}"], "Multiple units")
        self.assertEqual(cumulative["{{CUMULATIVE_TOTAL_ACTUAL}}"], "—")
        self.assertEqual(cumulative["{{CUMULATIVE_TOTAL_ACHIEVEMENT}}"], "—")

    def test_agent_analysis_is_used_in_slide_copy(self):
        current = payload()
        current["agent_analysis"] = {
            "performance_overview": "Agent-backed performance finding.",
            "content_analysis": "Agent-backed creative finding.",
            "optimisation_action": "Agent-backed next action.",
        }
        mapping = build_ads_mapping(current)
        self.assertEqual(mapping["{{PERFORMANCE_INSIGHT}}"], "Agent-backed performance finding.")
        self.assertEqual(mapping["{{BEST_CONTENT_1_INSIGHT}}"], "Agent-backed creative finding.")
        self.assertEqual(mapping["{{OPTIMIZATION_NEXT_STEP}}"], "Agent-backed next action.")

    def test_cumulative_overview_uses_history_values(self):
        current = payload()
        mapping = {}
        _fill_overview(mapping, [current], "CUMULATIVE")
        self.assertEqual(mapping["{{CUMULATIVE_ROW_1_EST_RESULT}}"], "80")
        self.assertEqual(mapping["{{CUMULATIVE_ROW_1_ACTUAL}}"], "70")
        self.assertEqual(mapping["{{CUMULATIVE_ROW_1_ACHIEVEMENT}}"], "87.5%")
        self.assertEqual(mapping["{{CUMULATIVE_ROW_1_SPENT}}"], "Rp 3,000,000")

    def test_adset_comparison_includes_budget_and_achievement(self):
        current = payload("link_clicks", "meta")
        current["rows"][0]["metrics"].update({"link_clicks": 500, "ctr": 2.5, "cpc": 200})
        current["objective_config"] = {
            "adset_targets": [{"adset_id": "ad-1", "target": 1000, "budget": 250000}]
        }
        mapping = {}
        _fill_comparison(mapping, current)
        self.assertEqual(mapping["{{COMPARE_METRIC_7_LABEL}}"], "Spend / Budget")
        self.assertEqual(mapping["{{COMPARE_ROW_7_COL_1}}"], "Rp 100,000 / Rp 250,000")
        self.assertEqual(mapping["{{COMPARE_METRIC_8_LABEL}}"], "Achievement vs. KPI")
        self.assertEqual(mapping["{{COMPARE_ROW_8_COL_1}}"], "0.9%")


if __name__ == "__main__":
    unittest.main()
