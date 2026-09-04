from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.utils.logger import node
from agentic.agents.ads_agent.ads_agent_creative.result_merge import merge_objective_result
from agentic.agents.ads_agent.ads_agent_creative.yt_impressions import yt_impressions_agent
from agentic.agents.ads_agent.ads_agent_creative.yt_views import yt_views_agent

def youtube_runner_node(state: State):
    with node("YouTube Ads Running"):
        combined = None
        for objective in state.request.objectives:
            key = str(objective).lower().strip().replace(" ", "_")
            if key in {"views", "video_views"}:
                result = yt_views_agent(state)
            elif key in {"impressions", "reach"}:
                result = yt_impressions_agent(state)
            else:
                continue
            value = result.get("youtube_result") if result else None
            if value is not None:
                combined = merge_objective_result(combined, value)
        return {"youtube_result": combined} if combined is not None else {}


def youtube_router(state: State):
    """Deprecated compatibility hook; objectives now run sequentially."""
    return []
