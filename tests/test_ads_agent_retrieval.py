from __future__ import annotations

import pytest

from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_data,
    retrieve_ads_sections,
)
from agentic.agents.ads_agent.ads_agent_creative import analysis_helpers
from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import ig_reach_agent
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    AdsRetrievalData,
    MetaData,
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
    objective_payload = payload["objective_data"]["leads"]
    assert objective_payload["summary"]["ctr"] is None
    assert objective_payload["rows"][0]["metrics"]["ctr"] is None
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
    assert state.request.objectives == ["leads"]


def test_request_accepts_multiple_objectives_and_legacy_singular():
    multiple = Request(
        client_code="bourbon",
        period_id="2026-07-01",
        analysis_type="creative",
        platform_scope="meta",
        objectives=["Reach", "engagement", "reach"],
    )
    legacy = Request(
        client_code="bourbon",
        period_id="2026-07-01",
        analysis_type="creative",
        platform_scope="meta",
        objective="reach",
    )

    assert multiple.objectives == ["reach", "engagement"]
    assert multiple.objective is None
    assert legacy.objectives == ["reach"]
    assert legacy.objective == "reach"


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
        objectives=["reach"],
        objective_data={
            "reach": {
                "status": "ready",
                "summary": {"reach": 10},
                "rows": [{"id": "ad-1", "metrics": {"reach": 10}}],
            }
        },
    )

    result = ig_reach_agent(state)["instagram_result"]
    assert result.performance_overview_reach == "ok"
    assert '"content_analysis": [' in captured["content"]
    assert '"id": "ad-1"' in captured["content"]
    assert '"analysis_sections": {' in captured["content"]
    parsed_context = __import__("json").loads(captured["content"])
    assert "rows" not in parsed_context["ads_data"]


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

    assert payload["status"] == "error"
    assert payload["success"] is False
    assert payload["rows"] == []
    assert payload["objective_data"]["leads"]["status"] == "objective_mismatch"
    assert "Confirm the campaign mapping" in payload["warnings"][0]


def test_meta_runner_preserves_each_objective_result(monkeypatch):
    from agentic.agents.ads_agent.ads_agent_creative.meta_runner_node import (
        meta_runner_node,
    )

    class FakeLLM:
        def invoke(self, messages):
            import json

            request = json.loads(messages[-1].content)
            objective = request["objective"]
            content = {
                key: f"{objective}:{key}"
                for key in request["required_output_keys"]
            }
            return type("Response", (), {"content": json.dumps(content)})()

    monkeypatch.setattr(analysis_helpers, "llm", FakeLLM())
    objective_data = {
        objective: {
            "status": "ready",
            "objective": objective,
            "summary": {},
            "rows": [{"id": f"ad-{objective}"}],
            "sections": {},
        }
        for objective in ("reach", "engagement", "link_clicks")
    }
    state = State(
        request=Request(
            client_code="bourbon",
            period_id="2026-07-01",
            analysis_type="creative",
            platform_scope="meta",
            objectives=["reach", "engagement", "link_clicks"],
        ),
        Metadata=MetaData(client_code="bourbon", instagram=True, facebook=True),
        ads_data=AdsRetrievalData(
            status="ready",
            success=True,
            objectives=["reach", "engagement", "link_clicks"],
            objective_data=objective_data,
        ),
    )

    result = meta_runner_node(state)
    instagram = result["instagram_result"]
    facebook = result["facebook_result"]

    assert instagram.objective is None
    assert instagram.objectives == ["reach", "engagement", "link_clicks"]
    assert set(instagram.objective_results) == {"reach", "engagement", "link_clicks"}
    assert instagram.objective_results["reach"].performance_overview.startswith("reach:")
    assert instagram.objective_results["engagement"].performance_overview.startswith("engagement:")
    assert instagram.objective_results["link_clicks"].performance_overview.startswith("link_clicks:")
    assert set(facebook.objective_results) == {"reach", "engagement", "link_clicks"}


@pytest.mark.parametrize("scope", ["meta", "instagram", "facebook"])
def test_workflow_runs_multiple_objectives_without_concurrent_updates(monkeypatch, scope):
    import json

    import agentic.agents.ads_agent.ads_agent_creative.summary_agent as summary_module
    import agentic.agents.ads_agent.ads_agent_creative.retrieval as retrieval_module
    from agentic.workflows.ads_workflow.ads_creative_workflow.graph import (
        creative_architecture,
    )

    class FakeLLM:
        def invoke(self, messages):
            request = json.loads(messages[-1].content)
            if "required_output_keys" in request:
                objective = request["objective"]
                content = {
                    key: f"{objective}:{key}"
                    for key in request["required_output_keys"]
                }
            else:
                content = {"summary_result": "ok"}
            return type("Response", (), {"content": json.dumps(content)})()

    def fake_retrieve_ads_data(**kwargs):
        objective_data = {
            objective: {
                "status": "ready",
                "success": True,
                "objective": objective,
                "summary": {},
                "rows": [{"id": f"ad-{objective}"}],
                "sections": {},
            }
            for objective in kwargs["objectives"]
        }
        return {
            "status": "ready",
            "success": True,
            "client": {
                "id": "client-id",
                "code": "bourbon",
                "name": "Bourbon",
                "ads_platforms": ["instagram", "facebook"],
            },
            "period": {"id": "period-id"},
            "analysis_type": "creative",
            "platform_scope": scope,
            "objectives": kwargs["objectives"],
            "objective_data": objective_data,
        }

    monkeypatch.setattr(analysis_helpers, "llm", FakeLLM())
    monkeypatch.setattr(summary_module, "llm", FakeLLM())
    monkeypatch.setattr(retrieval_module, "retrieve_ads_data", fake_retrieve_ads_data)

    request = Request(
        client_code="bourbon",
        period_id="2026-07-01",
        analysis_type="creative",
        platform_scope=scope,
        objectives=["reach", "engagement", "link_clicks"],
    )
    final = State.model_validate(creative_architecture.invoke(State(request=request)))

    expected = {"reach", "engagement", "link_clicks"}
    if scope in {"meta", "instagram"}:
        assert set(final.instagram_result.objective_results) == expected
    if scope in {"meta", "facebook"}:
        assert set(final.facebook_result.objective_results) == expected
    assert final.summary_result.summary_result == "ok"


def test_llm_rate_limit_is_retried_without_repeating_other_errors(monkeypatch):
    import agentic.utils.llm_retry as retry_module

    sleeps = []

    class RateLimitedOnce:
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED Please retry in 0.1s")
            return "ok"

    monkeypatch.setattr(retry_module.time, "sleep", sleeps.append)
    model = RateLimitedOnce()

    assert retry_module.invoke_with_rate_limit_retry(
        model,
        [],
        max_retries=1,
    ) == "ok"
    assert model.calls == 2
    assert sleeps == [2]


def test_llm_unavailable_is_retried_with_backoff(monkeypatch):
    import agentic.utils.llm_retry as retry_module

    sleeps = []

    class UnavailableTwice:
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("503 UNAVAILABLE model is experiencing high demand")
            return "ok"

    monkeypatch.setenv("ADS_LLM_UNAVAILABLE_RETRY_SECONDS", "1")
    monkeypatch.setattr(retry_module.time, "sleep", sleeps.append)
    model = UnavailableTwice()

    assert retry_module.invoke_with_rate_limit_retry(
        model,
        [],
        max_retries=2,
    ) == "ok"
    assert model.calls == 3
    assert sleeps == [2, 3]


def test_generic_objective_coerces_nested_llm_values_to_strings(monkeypatch):
    import json

    from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
        ig_generic_objective_agent,
    )

    class NestedResponseLLM:
        def invoke(self, messages):
            return type(
                "Response",
                (),
                {
                    "content": json.dumps(
                        {
                            "performance_overview": {"clicks": 10},
                            "content_analysis": [{"ad": "A"}],
                            "placement_analysis": None,
                            "audience_demographic_analysis": "Audience text",
                            "region_analysis": "Region text",
                            "optimisation_action": "Action text",
                        }
                    )
                },
            )()

    monkeypatch.setattr(analysis_helpers, "llm", NestedResponseLLM())
    state = State(
        request=Request(
            client_code="bourbon",
            period_id="2026-07-01",
            analysis_type="creative",
            platform_scope="instagram",
            objectives=["link_clicks"],
        ),
        Metadata=MetaData(client_code="bourbon", instagram=True),
        ads_data=AdsRetrievalData(
            status="ready",
            success=True,
            objectives=["link_clicks"],
            objective_data={
                "link_clicks": {
                    "status": "ready",
                    "summary": {"link_clicks": 10},
                    "rows": [{"id": "ad-1"}],
                }
            },
        ),
    )

    result = ig_generic_objective_agent(state, "link_clicks")["instagram_result"]
    assert result.performance_overview == '{"clicks": 10}'
    assert result.content_analysis == '[{"ad": "A"}]'


def test_transient_llm_failure_becomes_objective_error(monkeypatch):
    from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
        ig_generic_objective_agent,
    )
    from agentic.agents.ads_agent.ads_agent_creative.result_merge import (
        merge_objective_result,
    )

    class UnavailableLLM:
        def invoke(self, messages):
            raise RuntimeError("503 UNAVAILABLE model is experiencing high demand")

    monkeypatch.setenv("ADS_LLM_RATE_LIMIT_RETRIES", "0")
    monkeypatch.setattr(analysis_helpers, "llm", UnavailableLLM())
    state = State(
        request=Request(
            client_code="bourbon",
            period_id="2026-07-01",
            analysis_type="creative",
            platform_scope="instagram",
            objectives=["link_clicks"],
        ),
        Metadata=MetaData(client_code="bourbon", instagram=True),
        ads_data=AdsRetrievalData(
            status="ready",
            success=True,
            objectives=["link_clicks"],
            objective_data={"link_clicks": {"status": "ready", "rows": []}},
        ),
    )

    raw = ig_generic_objective_agent(state, "link_clicks")["instagram_result"]
    result = merge_objective_result(None, raw)

    assert result.objective_results["link_clicks"].status == "error"
    assert "unavailable" in result.objective_results["link_clicks"].error.lower()
