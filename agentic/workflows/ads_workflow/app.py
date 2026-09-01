from agentic.agents.ads_agent.router import router
from agentic.workflows.ads_workflow.ads_creative_workflow.graph import (
    creative_architecture
)

from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    Request as CreativeRequest,
    State as CreativeState
)


request = {
    "client_code": "bourbon",
    "period_id": "2026-07-01",
    "analysis_type": "creative",
    "platform_scope": "meta",
    "objective": "leads",
    "campaign_ids": [],
    "adset_ids": []
}


def run(request):
    route = router(request)

    print(f"\n[DEBUG] Route: {route}")

    if route == "creative":

        workflow_request = CreativeRequest(**request)

        initial_state = CreativeState(
            request=workflow_request
        )

        print("\n[DEBUG] INITIAL STATE")
        print(initial_state.model_dump())

        # LangGraph returns a mapping even when the graph state schema is a
        # Pydantic model.  Normalise it here so callers of ``run`` can use the
        # same State contract as the individual agents.
        result = creative_architecture.invoke(initial_state)
        result_state = CreativeState.model_validate(result)

        print("\n" + "=" * 60)
        print("[DEBUG] METADATA")
        print("=" * 60)

        metadata = result_state.Metadata

        print(metadata.model_dump())

        print("\n" + "=" * 60)
        print("[DEBUG] FINAL STATE")
        print("=" * 60)

        print(result_state.model_dump())

        return result_state

    elif route == "adset":
        pass


if __name__ == "__main__":
    run(request)
