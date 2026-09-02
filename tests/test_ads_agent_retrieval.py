from __future__ import annotations

from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_data,
    retrieve_ads_sections,
)
from agentic.agents.ads_agent.ads_agent_creative import analysis_helpers
from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import ig_reach_agent
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    AdsRetrievalData,
    Request,
    State,
)


class FakeDashboardClient:
    def __init__(self):
        self.analysis_calls = []

    def resolve_client_and_period(self, client_code, period_id):
        assert client_code == "bourbon"
        assert period_id == "2026-07-01"
        return (
            {
                "id": "client-id",
                "client_code": "bourbon",
                "client_name": "Bourbon",
                "ads_configuration": {"platforms": ["instagram", "facebook"]},
                "meta_ad_accounts": [{"id": "act_1", "name": "Bourbon Ads"}],
            },
            {
                "id": "period-id",
                "period_label": "July 2026",
                "period_start": "2026-07-01",
                "period_end": "2026-07-31",
            },
        )

    def get_analysis(self, **kwargs):
        self.analysis_calls.append(kwargs)
        return {
            "data_status": "ready",
            "dimension": kwargs["analysis_type"],
            "platform_scope": kwargs["platform_scope"],
            "objective": kwargs["objective"],
            "objectives": [kwargs["objective"]],
            "source": {"type": "api", "import_id": "import-id"},
            "summary": {"reach": 100, "ctr": None},
            "rows": [{"id": "ad-1", "metrics": {"reach": 100, "ctr": None}}],
            "display_metrics": [{"key": "reach"}],
            "available_filters": {"campaigns": [], "adsets": []},
            "warnings": [],
            "unconfirmed_count": 0,
        }


def test_retrieval_returns_canonical_payload_and_preserves_nulls():
    api = FakeDashboardClient()
    payload = retrieve_ads_data(
        client_code="bourbon",
        period_id="2026-07-01",
        analysis_type="creative",
        platform_scope="instagram",
        objective="leads",
        campaign_ids=["campaign-1"],
        client=api,
    )

    assert payload["status"] == "ready"
    assert payload["client"]["name"] == "Bourbon"
    assert payload["summary"]["ctr"] is None
    assert payload["rows"][0]["metrics"]["ctr"] is None
    assert api.analysis_calls[0]["client_id"] == "client-id"
    assert api.analysis_calls[0]["period_id"] == "period-id"
    assert api.analysis_calls[0]["campaign_ids"] == ["campaign-1"]


def test_retrieval_sections_split_dashboard_payload_by_analysis_area():
    payload = {
        "summary": {"result": 12, "spend": 100},
        "rows": [{"id": "ad-1", "name": "Top ad"}],
        "breakdowns": {
            "ad-1": {
                "creative": {"ad_name": "Top ad"},
                "placements": [{"placement": "Feed", "impressions": 10}],
                "demographics": [{"age": "25-34", "gender": "female", "reach": 8}],
                "regions": [{"region": "Jakarta", "reach": 5}],
            }
        },
    }

    sections = retrieve_ads_sections(payload)

    assert sections["performance_overview"] == {"result": 12, "spend": 100}
    assert sections["content_analysis"] == [{"id": "ad-1", "name": "Top ad"}]
    assert sections["placement_analysis"][0]["entity_name"] == "Top ad"
    assert sections["audience_demographic_analysis"][0]["gender"] == "female"
    assert sections["region_analysis"][0]["region"] == "Jakarta"


def test_state_has_typed_ads_data_contract():
    state = State(
        request=Request(
            client_code="bourbon",
            period_id="2026-07-01",
            analysis_type="creative",
            platform_scope="meta",
            objective="leads",
        )
    )
    state.ads_data = AdsRetrievalData(status="ready", rows=[{"id": "ad-1"}])
    assert state.ads_data.status == "ready"
    assert state.ads_data.rows == [{"id": "ad-1"}]


def test_unavailable_platform_is_explicitly_coming_soon():
    api = FakeDashboardClient()
    payload = retrieve_ads_data(
        client_code="bourbon",
        period_id="2026-07-01",
        platform_scope="tiktok",
        objective="views",
        client=api,
    )
    assert payload["status"] == "coming_soon"
    assert payload["success"] is False
    assert payload["rows"] == []
    assert "coming soon" in payload["warnings"][0].lower()
    assert api.analysis_calls == []


def test_objective_agent_consumes_state_as_json_context(monkeypatch):
    captured = {}

    class FakeLLM:
        def invoke(self, messages):
            captured["content"] = messages[1].content
            return type(
                "Response",
                (),
                {
                    "content": '{"performance_overview_reach":"ok","content_analysis_reach":"ok","placement_analysis_reach":"ok","audience_demographic_analysis_reach":"ok","region_analysis_reach":"ok","optimisation_action_reach":"ok"}'
                },
            )()

    monkeypatch.setattr(analysis_helpers, "llm", FakeLLM())
    state = State(
        request=Request(
            client_code="bourbon",
            period_id="2026-07-01",
            analysis_type="creative",
            platform_scope="instagram",
            objective="reach",
        )
    )
    state.Metadata.client_code = "bourbon"
    state.ads_data = AdsRetrievalData(
        status="ready",
        summary={"reach": 10},
        rows=[{"id": "ad-1", "metrics": {"reach": 10}}],
    )

    result = ig_reach_agent(state)["instagram_result"]
    assert result.performance_overview_reach == "ok"
    assert '"rows": [' in captured["content"]
    assert '"id": "ad-1"' in captured["content"]
    assert '"analysis_sections": {' in captured["content"]


def test_retrieval_rejects_dashboard_objective_fallback():
    class FallbackClient(FakeDashboardClient):
        def get_analysis(self, **kwargs):
            response = super().get_analysis(**kwargs)
            response["objective"] = "reach"
            return response

    payload = retrieve_ads_data(
        client_code="bourbon",
        period_id="2026-07-01",
        analysis_type="creative",
        platform_scope="instagram",
        objective="leads",
        client=FallbackClient(),
    )

    assert payload["status"] == "objective_mismatch"
    assert payload["success"] is False
    assert payload["rows"] == []
    assert "Confirm the campaign mapping" in payload["warnings"][0]
