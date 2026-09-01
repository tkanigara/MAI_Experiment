from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def tiktok_runner_node(state: State):
    with node("TikTok Ads Running"):
        return state


def tiktok_router(state: State):
    return [
        Send("tiktok_views", state),
        Send("tiktok_follow", state),
    ]