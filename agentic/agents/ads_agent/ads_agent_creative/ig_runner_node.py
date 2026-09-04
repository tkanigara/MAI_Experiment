from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
    ig_generic_objective_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.ig_engagement_agent import ig_engagement_agent
from agentic.agents.ads_agent.ads_agent_creative.ig_profilevisit_agent import ig_profilevisit_agent
from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import ig_reach_agent
from agentic.agents.ads_agent.ads_agent_creative.result_merge import merge_objective_result
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State


def _objective_keys(state: State) -> list[str]:
    return [
        str(objective).lower().strip().replace(" ", "_")
        for objective in state.request.objectives
        if str(objective).strip()
    ]


def instagram_runner_node(state: State):
    """Run Instagram objectives sequentially to avoid LangGraph conflicts."""

    with node("Instagram Ads Running"):
        agents = {
            "reach": ig_reach_agent,
            "engagement": ig_engagement_agent,
            "profile_visit": ig_profilevisit_agent,
            "profile_visits": ig_profilevisit_agent,
            "profilevisit": ig_profilevisit_agent,
        }
        combined = None
        for objective in _objective_keys(state):
            agent = agents.get(objective)
            result = agent(state) if agent else ig_generic_objective_agent(state, objective)
            value = result.get("instagram_result") if result else None
            if value is not None:
                combined = merge_objective_result(combined, value)
        return {"instagram_result": combined} if combined is not None else {}


def instagram_router(state: State):
    """Deprecated compatibility hook; objectives now run sequentially."""
    return []
