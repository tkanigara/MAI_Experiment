from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def instagram_runner_node(state: State):
    with node("Instagram Ads Running"):
        return state


def instagram_router(state: State):
    return [
        Send("instagram_reach_agent", state),
        Send("instagram_engagement_agent", state),
        Send("instagram_profilevisit_agent", state),
    ]