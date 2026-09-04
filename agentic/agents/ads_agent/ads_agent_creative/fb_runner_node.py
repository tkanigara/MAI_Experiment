from agentic.agents.ads_agent.ads_agent_creative.fb_engagement_agent import fb_engagement_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_pagelike_agent import fb_pagelike_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_profilevisit import fb_profilevisit_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_reach_agent import fb_reach_agent
from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
    fb_generic_objective_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.result_merge import merge_objective_result
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State


def _objective_keys(state: State) -> list[str]:
    return [
        str(objective).lower().strip().replace(" ", "_")
        for objective in state.request.objectives
        if str(objective).strip()
    ]


def facebook_runner_node(state: State):
    """Run Facebook objectives sequentially to avoid LangGraph conflicts."""

    with node("Facebook Ads Running"):
        agents = {
            "reach": fb_reach_agent,
            "engagement": fb_engagement_agent,
            "profile_visit": fb_profilevisit_agent,
            "profile_visits": fb_profilevisit_agent,
            "profilevisit": fb_profilevisit_agent,
            "page_like": fb_pagelike_agent,
            "page_likes": fb_pagelike_agent,
            "pagelike": fb_pagelike_agent,
        }
        combined = None
        for objective in _objective_keys(state):
            agent = agents.get(objective)
            result = agent(state) if agent else fb_generic_objective_agent(state, objective)
            value = result.get("facebook_result") if result else None
            if value is not None:
                combined = merge_objective_result(combined, value)
        return {"facebook_result": combined} if combined is not None else {}


def facebook_router(state: State):
    """Deprecated compatibility hook; objectives now run sequentially."""
    return []
