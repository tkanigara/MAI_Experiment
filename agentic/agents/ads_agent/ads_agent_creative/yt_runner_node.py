from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def youtube_runner_node(state: State):
    with node("YouTube Ads Running"):
        return state


def youtube_router(state: State):
    return [
        Send("youtube_impressions_agent", state),
        Send("youtube_views_agent", state),
    ]