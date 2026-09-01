from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def youtube_runner_node(state: State):
    with node("YouTube Ads Running"):
        return state


def youtube_router(state: State):
    objective = str(state.request.objective or "").lower().strip().replace(" ", "_")
    route = "youtube_views_agent" if objective in {"views", "video_views"} else "youtube_impressions_agent"
    return [Send(route, state)]
