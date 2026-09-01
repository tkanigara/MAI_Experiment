from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from langgraph.constants import Send
from agentic.utils.logger import node

def facebook_runner_node(state: State):
    with node("Facebook Ads Running"):
        return state


def facebook_router(state: State):
    objective = str(state.request.objective or "").lower().strip().replace(" ", "_")
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
    route = routes.get(objective, "facebook_generic_objective_agent")
    return [Send(route, state)] if route else []
