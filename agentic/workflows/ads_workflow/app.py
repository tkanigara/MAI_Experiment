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

        result = creative_architecture.invoke(initial_state)

        print("\n" + "=" * 60)
        print("[DEBUG] METADATA")
        print("=" * 60)

        metadata = result.Metadata

        print(metadata.model_dump())

        print("\n" + "=" * 60)
        print("[DEBUG] FINAL STATE")
        print("=" * 60)

        print(result.model_dump())

        return result

    elif route == "adset":
        pass


if __name__ == "__main__":
    run(request)