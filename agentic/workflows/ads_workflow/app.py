from typing import Any
from agentic.workflows.ads_workflow.ads_creative_workflow.graph import creative_architecture
from agentic.workflows.ads_workflow.adset_workflow.graph import graph
from agentic.agents.ads_agent.router import router

def run(request: dict[str, Any]):
    analysis_type = router(request)
    
    if analysis_type == "creative":
        return creative_architecture.invoke({
            "request":request
        })
    elif analysis_type == "adset":
        return graph.invoke({
            "request": request
        })

if __name__ == "__main__":

    request = {
        "client_code": "jba",
        "period_id": "2026-08-01",
        "analysis_type": "creative",
        "platform_scope": [
            "instagram",
        ],
        "objectives": [
            "reach",
            "profilevisit"
        ],
        "campaign_ids": [],
        "adset_ids": [],
        "include_breakdowns": True,
    }

    result = run(request)

