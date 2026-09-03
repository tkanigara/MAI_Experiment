from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def facebook_runner_node(state: State):
    with node("Facebook Ads Running"):
        return state


def facebook_router(state: State):

    objectives = [
        str(objective)
        .lower()
        .strip()
        .replace(" ", "_")
        for objective in state.request.objectives
    ]

    routes = {
        "reach": "facebook_reach_agent",

        "engagement": "facebook_engagement_agent",

        "profile_visit": "facebook_profilevisit_agent",
        "profile_visits": "facebook_profilevisit_agent",
        "profilevisit": "facebook_profilevisit_agent",

        "page_like": "facebook_pagelike_agent",
        "page_likes": "facebook_pagelike_agent",
        "pagelike": "facebook_pagelike_agent",
    }

    sends = []

    for objective in objectives:

        route = routes.get(objective)

        if route:
            sends.append(
                Send(route, state)
            )

    return sends