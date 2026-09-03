from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def instagram_runner_node(state: State):
    with node("Instagram Ads Running"):
        return state


def instagram_router(state: State):

    objectives = [
        str(objective).lower().strip().replace(" ", "_")
        for objective in state.request.objectives
    ]

    routes = {
        "reach": "instagram_reach_agent",

        "engagement": "instagram_engagement_agent",

        "profile_visit": "instagram_profilevisit_agent",
        "profile_visits": "instagram_profilevisit_agent",
        "profilevisit": "instagram_profilevisit_agent",
    }

    sends = []

    for objective in objectives:

        route = routes.get(objective)

        if route:
            sends.append(
                Send(route, state)
            )

    return sends
