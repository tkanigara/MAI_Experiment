from __future__ import annotations

import json

from agentic.agents.ads_agent.ads_agent_creative import analysis_helpers
from agentic.agents.ads_agent.ads_set_agent.data_source import get_adset_evidence
from agentic.services.ads_services.adset_service import AdSetAdsService
from agentic.services.ads_services.creative_service import CreativeAdsService
from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_data,
    retrieve_ads_sections,
)
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    AdsRetrievalData,
    InstagramMetricAnalysis,
    MetaData,
    Request as CreativeRequest,
    State as CreativeState,
)
from agentic.workflows.ads_workflow.adset_workflow.state import (
    Request as AdSetRequest,
    State as AdSetState,
)


class FakeDashboardClient:
    def __init__(self, creative_import_id: str = "import-1"):
        self.creative_import_id = creative_import_id
        self.creative_calls = []
        self.adset_calls = []

    def resolve_client_and_period(self, client_code, period_id):
        return (
            {
                "id": "client-id",
                "client_code": client_code,
                "client_name": "JBA",
                "ads_configuration": {"platforms": ["instagram", "facebook"]},
                "meta_ad_accounts": [],
            },
            {
                "id": "period-id",
                "period_label": "July 2026",
                "period_start": "2026-07-01",
                "period_end": "2026-07-31",
            },
        )

    def get_analysis(self, **kwargs):
        return self._creative_response()

    def get_creative_performance(self, **kwargs):
        self.creative_calls.append(kwargs)
        return self._creative_response()

    def get_adset_performance(self, **kwargs):
        self.adset_calls.append(kwargs)
        return {
            "data_status": "ready",
            "source": {"type": "api", "import_id": "import-1"},
            "summary": {"result": 12, "reach": 100, "spend": 50000},
            "rows": [
                {
                    "id": "adset-1",
                    "name": "Beli Unit Audience",
                    "campaign_id": "campaign-1",
                    "campaign_name": "Leads Campaign",
                    "metrics": {"result": 12, "reach": 100, "spend": 50000},
                }
            ],
            "display_metrics": [{"key": "result"}, {"key": "reach"}],
            "kpi": {"target": 20},
            "warnings": [],
        }

    def _creative_response(self):
        return {
            "data_status": "ready",
            "dimension": "creative",
            "source": {"type": "api", "import_id": self.creative_import_id},
            "summary": {"result": 12, "reach": 100, "ctr": None},
            "rows": [
                {
                    "id": "ad-1",
                    "name": "Creative One",
                    "adset_id": "adset-1",
                    "metrics": {"result": 12, "reach": 100, "ctr": None},
                }
            ],
            "display_metrics": [{"key": "result"}, {"key": "reach"}],
            "available_filters": {"campaigns": [], "adsets": []},
            "kpi": {"target": 20},
            "warnings": [],
            "unconfirmed_count": 0,
        }


def test_dashboard_retrieval_preserves_null_values():
    payload = retrieve_ads_data(
        client_code="jba",
        period_id="2026-07-01",
        analysis_type="creative",
        platform_scope="instagram",
        objectives=["leads"],
        client=FakeDashboardClient(),
    )
    objective = payload["objective_data"]["leads"]
    assert objective["summary"]["ctr"] is None
    assert objective["rows"][0]["metrics"]["ctr"] is None


def test_retrieval_sections_are_local_projections():
    sections = retrieve_ads_sections(
        {
            "summary": {"result": 12},
            "rows": [{"id": "ad-1", "name": "Top ad"}],
            "breakdowns": {
                "ad-1": {
                    "creative": {"ad_name": "Top ad"},
                    "placements": [{"placement": "Feed", "impressions": 10}],
                    "demographics": [{"age": "25-34", "gender": "female"}],
                    "regions": [{"region": "Jakarta", "reach": 5}],
                }
            },
        }
    )
    assert sections["performance_overview"] == {"result": 12}
    assert sections["placement_analysis"][0]["entity_name"] == "Top ad"
    assert sections["audience_demographic_analysis"][0]["gender"] == "female"
    assert sections["region_analysis"][0]["region"] == "Jakarta"


def test_adset_service_returns_campaigns_and_creatives_from_same_snapshot():
    api = FakeDashboardClient()
    payload = AdSetAdsService(api).retrieve(
        "jba", "2026-07-01", "meta", "linkclicks"
    )
    data = payload["objective_data"]
    assert payload["objective"] == "link_clicks"
    assert data["objective_overview"]["campaigns"][0]["name"] == "Leads Campaign"
    assert data["adset_breakdowns"]["adset-1"]["creatives"][0]["id"] == "ad-1"
    assert api.adset_calls[0]["objective"] == "link_clicks"
    assert api.creative_calls[0]["adset_ids"] is None


def test_adset_service_rejects_cross_snapshot_creatives():
    payload = AdSetAdsService(FakeDashboardClient("import-2")).retrieve(
        "jba", "2026-07-01", "meta", "leads"
    )
    data = payload["objective_data"]
    assert data["adset_breakdowns"]["adset-1"]["creatives"] == []
    assert "same active snapshot" in data["warnings"][-1]


def test_creative_service_normalises_legacy_objective_aliases():
    api = FakeDashboardClient()
    payload = CreativeAdsService(api).retrieve(
        "jba", "2026-07-01", "facebook", "pagelike"
    )
    assert payload["objective"] == "page_likes"
    assert api.creative_calls[0]["objective"] == "page_likes"


def test_adset_agent_prefers_frozen_evidence():
    frozen = {"objective": "leads", "objective_data": {"source": {"import_id": "1"}}}
    state = AdSetState(
        request=AdSetRequest(
            client_code="jba",
            period_id="period-id",
            analysis_type="adset",
            platform_scope=["meta"],
            objectives=["leads"],
        ),
        adset_data={"leads": frozen},
    )

    class RetrievalMustNotRun:
        def invoke(self, _):
            raise AssertionError("dashboard was queried again")

    assert get_adset_evidence(state, "leads", RetrievalMustNotRun()) == frozen


def test_creative_analysis_helper_uses_only_frozen_sections(monkeypatch):
    captured = {}

    def fake_invoke(_llm, messages, **_kwargs):
        captured["context"] = json.loads(messages[-1].content)
        return type("Response", (), {"content": '{"performance_overview":"supported"}'})()

    monkeypatch.setattr(analysis_helpers, "invoke_with_rate_limit_retry", fake_invoke)
    state = CreativeState(
        request=CreativeRequest(
            client_code="jba",
            period_id="period-id",
            analysis_type="creative",
            platform_scope=["instagram"],
            objectives=["leads"],
        ),
        Metadata=MetaData(client_code="jba"),
        ads_data=AdsRetrievalData(
            status="ready",
            success=True,
            objective_data={
                "leads": {
                    "status": "ready",
                    "sections": {"performance_overview": {"result": 12}},
                }
            },
        ),
    )
    result = analysis_helpers.run_ads_analysis_agent(
        state,
        objective="leads",
        system_prompt=None,
        result_model=InstagramMetricAnalysis,
        result_field="instagram_result",
        output_fields=["performance_overview"],
        label="test",
    )
    assert result["instagram_result"].performance_overview == "supported"
    assert captured["context"]["analysis_sections"]["performance_overview"]["result"] == 12


def test_adset_slide_analysis_uses_friend_workflow_and_frozen_payload(monkeypatch):
    import agentic.agents.ads_agent.ads_set_agent.meta_leads_agent as leads_module
    import agentic.agents.ads_agent.ads_set_agent.meta_summary as summary_module
    from dashboard.ads_slides_report import _run_adset_agent_analysis

    captured = []

    class FakeLLM:
        def invoke(self, messages):
            captured.append(json.loads(messages[-1].content))
            if "final Meta Ads reporting analyst" in messages[0].content:
                content = {"summary_result": "prioritise the efficient ad set"}
            else:
                content = {
                    "overall_leads_analysis": "12 leads overall",
                    "leads_adset_analysis": "Beli Unit Audience led the result",
                }
            return type("Response", (), {"content": json.dumps(content)})()

    monkeypatch.setattr(leads_module, "llm", FakeLLM())
    monkeypatch.setattr(summary_module, "llm", FakeLLM())
    payload = {
        "model": "jba",
        "objective": "leads",
        "platform_scope": "meta",
        "client": {"id": "client-id", "client_code": "jba", "client_name": "JBA"},
        "period": {"id": "period-id"},
        "source": {"type": "api", "import_id": "import-1"},
        "analysis": {
            "data_status": "ready",
            "summary": {"result": 12},
            "display_metrics": [{"key": "result"}],
            "warnings": [],
        },
        "analysis_sections": {
            "objective_overview": {
                "summary": {"result": 12},
                "campaigns": [],
                "adsets": [{"id": "adset-1", "name": "Beli Unit Audience"}],
            }
        },
        "adset_breakdowns": {
            "adset-1": {"creatives": [{"id": "ad-1", "name": "Creative One"}]}
        },
    }
    result = _run_adset_agent_analysis(payload)
    assert result["performance_overview"] == "12 leads overall"
    assert result["adset_analysis"] == "Beli Unit Audience led the result"
    assert result["optimisation_action"] == "prioritise the efficient ad set"
    assert captured[0]["objective_data"]["source"]["import_id"] == "import-1"
