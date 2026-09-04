from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.utils.logger import node
from agentic.agents.ads_agent.ads_agent_creative.result_merge import merge_objective_result
from agentic.agents.ads_agent.ads_agent_creative.tt_follow import tt_follow_agent
from agentic.agents.ads_agent.ads_agent_creative.tt_views_agent import tt_views_agent

def tiktok_runner_node(state: State):
    with node("TikTok Ads Running"):
        combined = None
        for objective in state.request.objectives:
            key = str(objective).lower().strip().replace(" ", "_")
            if key in {"community_interaction", "paid_follow", "follow", "paid_follows"}:
                result = tt_follow_agent(state)
            elif key in {"views", "video_views"}:
                result = tt_views_agent(state)
            else:
                continue
            value = result.get("tiktok_result") if result else None
            if value is not None:
                combined = merge_objective_result(combined, value)
        return {"tiktok_result": combined} if combined is not None else {}


def tiktok_router(state: State):
    """Deprecated compatibility hook; objectives now run sequentially."""
    return []
