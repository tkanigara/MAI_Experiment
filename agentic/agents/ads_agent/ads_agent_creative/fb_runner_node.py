from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def facebook_runner_node(state: State):
    with node("Facebook Ads Running"):
        return state


def facebook_router(state: State):
    return [
        Send("facebook_reach_agent", state),
        Send("facebook_engagement_agent", state),
        Send("facebook_profilevisit_agent", state),
        Send("facebook_pagelike_agent", state),
    ]