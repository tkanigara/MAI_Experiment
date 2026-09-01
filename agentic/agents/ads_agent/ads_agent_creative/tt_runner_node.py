from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def tiktok_runner_node(state: State):
    with node("TikTok Ads Running"):
        return state


def tiktok_router(state: State):
    objective = str(state.request.objective or "").lower().strip().replace(" ", "_")
    route = "tiktok_follow" if objective in {"community_interaction", "paid_follow", "follow", "paid_follows"} else "tiktok_views"
    return [Send(route, state)]
