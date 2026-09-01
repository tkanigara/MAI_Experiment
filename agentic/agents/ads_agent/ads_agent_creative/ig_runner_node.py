from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def instagram_runner_node(state: State):
    with node("Instagram Ads Running"):
        return state


def instagram_router(state: State):
    objective = str(state.request.objective or "").lower().strip().replace(" ", "_")
    routes = {
        "reach": "instagram_reach_agent",
        "engagement": "instagram_engagement_agent",
        "profile_visit": "instagram_profilevisit_agent",
        "profile_visits": "instagram_profilevisit_agent",
        "profilevisit": "instagram_profilevisit_agent",
    }
    route = routes.get(objective, "instagram_generic_objective_agent")
    return [Send(route, state)] if route else []
