import unittest
from unittest.mock import patch

from dashboard.ads_slides_report import (
    ARCHETYPE,
    _fill_adset,
    _fill_comparison,
    _fill_overview,
    _goal_breakdown,
    _run_agent_analysis,
    _slide_plan,
    _table_trim_requests,
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
        self.assertEqual(mapping["{{BEST_CONTENT_ANALYSIS}}"], "Agent-backed creative finding.")
        self.assertNotIn("Agent-backed next action.", mapping["{{BEST_CONTENT_ANALYSIS}}"])
        self.assertEqual(mapping["{{BEST_CONTENT_2_INSIGHT}}"], "")
        self.assertEqual(mapping["{{OPTIMIZATION_NEXT_STEP}}"], "Agent-backed next action.")

    def test_agent_narratives_are_not_shortened_for_report_slides(self):
        current = payload()
        long_finding = "finding " * 150
        current["agent_analysis"] = {
            "performance_overview": long_finding,
            "content_analysis": long_finding,
            "placement_analysis": long_finding,
            "optimisation_action": long_finding,
        }
        mapping = build_ads_mapping(current)
        self.assertEqual(mapping["{{PERFORMANCE_INSIGHT}}"], long_finding.strip())
        self.assertEqual(mapping["{{BEST_CONTENT_ANALYSIS}}"], long_finding.strip())
        self.assertEqual(mapping["{{OPTIMIZATION_NEXT_STEP}}"], long_finding.strip())

    def test_missing_row_metric_displays_zero_instead_of_a_dash(self):
        current = payload()
        current["metric_keys"] = ["post_saves"]
        current["rows"][0]["metrics"]["post_saves"] = None
        mapping = build_ads_mapping(current)
        self.assertEqual(mapping["{{CREATIVE_ROW_1_METRIC_1}}"], "0")

    def test_dunlop_creative_and_breakdowns_paginate_all_available_rows(self):
        current = payload()
        current["rows"] = current["rows"] + [
            {
                "id": f"extra-{index}",
                "name": f"Extra Creative {index}",
                "campaign_name": "Campaign A",
                "adset_name": "Audience A",
                "metrics": {"result": index, "reach": index * 100, "impressions": index * 120, "spend": index * 1000},
            }
            for index in range(1, 10)
        ]
        current["breakdown"]["regions"] = [
            {"label": f"Region {index}", "result": index, "impressions": index * 100}
            for index in range(1, 11)
        ]
        plans = _slide_plan([current], "dunlop")
        creative_plans = [plan for plan in plans if plan["source"] == ARCHETYPE["creative"]]
        breakdown_plans = [plan for plan in plans if plan["source"] == ARCHETYPE["breakdown"]]
        self.assertEqual(len(creative_plans), 3)
        self.assertEqual(creative_plans[-1]["mapping"]["{{CREATIVE_ROW_4_NAME}}"], "Extra Creative 9")
        self.assertEqual(creative_plans[-1]["table_trim"]["data_rows"], 4)
        self.assertEqual(len(breakdown_plans), 4)
        self.assertEqual(breakdown_plans[-1]["table_trim"]["data_rows"], 4)

    def test_table_trim_deletes_only_unused_data_rows_and_metric_columns(self):
        plans = [{"slide_id": "output-slide", "table_trim": {"data_rows": 3, "metric_columns": 2}}]
        presentation = {
            "slides": [{
                "objectId": "output-slide",
                "pageElements": [{
                    "objectId": "output-table",
                    "table": {"columns": 5, "tableRows": [{}, {}, {}, {}, {}, {}, {}]},
                }],
            }]
        }
        requests = _table_trim_requests(presentation, plans)
        deleted_rows = [request["deleteTableRow"]["cellLocation"]["rowIndex"] for request in requests if "deleteTableRow" in request]
        deleted_columns = [request["deleteTableColumn"]["cellLocation"]["columnIndex"] for request in requests if "deleteTableColumn" in request]
        self.assertEqual(deleted_rows, [5, 4])
        self.assertEqual(deleted_columns, [4, 3])

    def test_dunlop_plan_keeps_all_three_breakdown_slides_when_a_cut_is_empty(self):
        current = payload()
        current["breakdown"] = {"placements": [], "demographics": [], "regions": []}
        plans = _slide_plan([current], "dunlop")
        sources = [plan["source"] for plan in plans]
        self.assertEqual(sources.count(ARCHETYPE["breakdown"]), 3)

    def test_platform_report_uses_shared_meta_audience_breakdowns(self):
        class FakeRepo:
            def platform_detail(self, *_args):
                return {"goals": [{"key": "reach", "placements": [], "demographics": [], "regions": []}]}

            def shared_audience_breakdowns(self, *_args):
                return {
                    "scope": "shared_meta",
                    "demographics": [{"age": "25-34", "gender": "female", "reach": 10}],
                    "regions": [{"label": "Jakarta", "reach": 8}],
                }

        result = _goal_breakdown(FakeRepo(), "client", "period", "instagram", "reach")
        self.assertEqual(result["demographics"][0]["label"], "All Meta | 25-34 | Female")
        self.assertEqual(result["regions"][0]["label"], "All Meta | Jakarta")

    def test_dunlop_agent_accepts_platform_scope_and_returns_slide_fields(self):
        current = payload()
        current["client"]["client_code"] = "example-client"
        current["analysis_sections"] = {
            "performance_overview": {"result": 35},
            "content_analysis": current["rows"],
            "placement_analysis": current["breakdown"]["placements"],
            "audience_demographic_analysis": current["breakdown"]["demographics"],
            "region_analysis": current["breakdown"]["regions"],
        }
        response = type(
            "Response",
            (),
            {
                "content": (
                    '{"performance_overview":"overview","content_analysis":"content",'
                    '"placement_analysis":"placement","audience_demographic_analysis":"audience",'
                    '"region_analysis":"region","optimisation_action":"action"}'
                )
            },
        )()
        with patch(
            "agentic.agents.ads_agent.ads_agent_creative.analysis_helpers.invoke_with_rate_limit_retry",
            return_value=response,
        ):
            result = _run_agent_analysis(current)
        self.assertEqual(result["content_analysis"], "content")
        self.assertEqual(result["audience_demographic_analysis"], "audience")
        self.assertEqual(result["region_analysis"], "region")

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

    def test_jba_plan_covers_every_adset_and_paginates_comparison(self):
        current = payload("leads", "meta")
        current["model"] = "jba"
        current["rows"] = [
            {
                "id": f"set-{index}",
                "name": f"Audience {index}",
                "campaign_name": "Campaign A",
                "metrics": {"result": 10 - index, "reach": 1000 * index},
            }
            for index in range(1, 7)
        ]
        creative_rows = [
            {
                "id": f"creative-{index}",
                "name": f"Creative {index}",
                "adset_id": f"set-{index}",
                "adset_name": f"Audience {index}",
                "campaign_name": "Campaign A",
                "metrics": {"result": 10 - index, "reach": 1000 * index},
            }
            for index in range(1, 7)
        ]
        current["creative_analysis"] = {
            "data_status": "ready",
            "summary": {"result": 39},
            "rows": creative_rows,
            "source": current["source"],
        }
        current["adset_breakdowns"] = {
            f"set-{index}": {
                "adset": current["rows"][index - 1],
                "creatives": [creative_rows[index - 1]],
                "source": current["source"],
            }
            for index in range(1, 7)
        }

        plans = _slide_plan([current], "jba")
        sources = [plan["source"] for plan in plans]
        self.assertEqual(sources.count(ARCHETYPE["comparison"]), 2)
        self.assertEqual(sources.count(ARCHETYPE["adset"]), 6)
        adset_mappings = [plan["mapping"] for plan in plans if plan["source"] == ARCHETYPE["adset"]]
        self.assertIn("Audience 6", adset_mappings[-1]["{{ADSET_NAME}}"])
        self.assertIn("Campaign A", adset_mappings[-1]["{{ADSET_NAME}}"])

    def test_jba_plan_paginates_all_creatives_inside_an_adset(self):
        current = payload("leads", "meta")
        current["model"] = "jba"
        adset = {
            "id": "set-1",
            "name": "Audience 1",
            "campaign_name": "Campaign A",
            "metrics": {"result": 21, "reach": 6000},
        }
        creatives = [
            {
                "id": f"creative-{index}",
                "name": f"Creative {index}",
                "adset_id": "set-1",
                "adset_name": "Audience 1",
                "campaign_name": "Campaign A",
                "metrics": {"result": index, "reach": index * 100},
            }
            for index in range(1, 7)
        ]
        current["rows"] = [adset]
        current["creative_analysis"] = {
            "data_status": "ready",
            "summary": {"result": 21},
            "rows": creatives,
            "source": current["source"],
        }
        current["adset_breakdowns"] = {
            "set-1": {"adset": adset, "creatives": creatives, "source": current["source"]}
        }

        plans = _slide_plan([current], "jba")
        adset_mappings = [plan["mapping"] for plan in plans if plan["source"] == ARCHETYPE["adset"]]
        self.assertEqual(len(adset_mappings), 2)
        self.assertEqual(adset_mappings[0]["{{AD_ROW_5_NAME}}"], "Creative 5")
        self.assertEqual(adset_mappings[1]["{{AD_ROW_1_NAME}}"], "Creative 6")
        self.assertIn("Part 2/2", adset_mappings[1]["{{ADSET_NAME}}"])


if __name__ == "__main__":
    unittest.main()
