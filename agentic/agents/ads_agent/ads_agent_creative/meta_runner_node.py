"""Sequential runner for an All Meta analysis.

LangGraph's ``Send`` creates parallel branches.  Passing the full Pydantic
state to both Instagram and Facebook branches causes a concurrent update
conflict on immutable fields such as ``request``.  All Meta is one logical
analysis, so run the two platform agents sequentially in one node instead.
"""

from __future__ import annotations

from agentic.agents.ads_agent.ads_agent_creative.fb_engagement_agent import fb_engagement_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_pagelike_agent import fb_pagelike_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_profilevisit import fb_profilevisit_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_reach_agent import fb_reach_agent
from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
    fb_generic_objective_agent,
    ig_generic_objective_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.ig_engagement_agent import ig_engagement_agent
from agentic.agents.ads_agent.ads_agent_creative.ig_profilevisit_agent import ig_profilevisit_agent
from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import ig_reach_agent
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State


def _objective_key(state: State) -> str:
    return str(state.request.objective or "").lower().strip().replace(" ", "_")


def meta_runner_node(state: State) -> dict:
    """Run the selected objective once for Instagram and once for Facebook."""

    with node("All Meta Ads Running"):
        objective = _objective_key(state)
        instagram_agents = {
            "reach": ig_reach_agent,
            "engagement": ig_engagement_agent,
            "profile_visit": ig_profilevisit_agent,
            "profile_visits": ig_profilevisit_agent,
            "profilevisit": ig_profilevisit_agent,
        }
        facebook_agents = {
            "reach": fb_reach_agent,
            "engagement": fb_engagement_agent,
            "profile_visit": fb_profilevisit_agent,
            "profile_visits": fb_profilevisit_agent,
            "profilevisit": fb_profilevisit_agent,
            "page_like": fb_pagelike_agent,
            "page_likes": fb_pagelike_agent,
            "pagelike": fb_pagelike_agent,
        }
        instagram_result = instagram_agents.get(objective, ig_generic_objective_agent)(state)
        facebook_result = facebook_agents.get(objective, fb_generic_objective_agent)(state)
        return {**instagram_result, **facebook_result}

