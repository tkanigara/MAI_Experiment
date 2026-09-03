from __future__ import annotations

from agentic.agents.ads_agent.ads_agent_creative.fb_engagement_agent import (
    fb_engagement_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.fb_pagelike_agent import (
    fb_pagelike_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.fb_profilevisit import (
    fb_profilevisit_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.fb_reach_agent import (
    fb_reach_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
    fb_generic_objective_agent,
    ig_generic_objective_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.ig_engagement_agent import (
    ig_engagement_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.ig_profilevisit_agent import (
    ig_profilevisit_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import (
    ig_reach_agent,
)

from agentic.utils.logger import node

from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    FacebookMetricAnalysis,
    InstagramMetricAnalysis,
    State,
)


def _objective_keys(state: State) -> list[str]:
    """
    Normalize all requested objectives.

    Example:
        [
            "reach",
            "engagement",
            "profilevisit"
        ]
    """

    return [
        str(objective)
        .lower()
        .strip()
        .replace(" ", "_")
        for objective in state.request.objectives
        if str(objective).strip()
    ]


def _merge_instagram_result(
    current: InstagramMetricAnalysis | None,
    new_result: InstagramMetricAnalysis,
) -> InstagramMetricAnalysis:
    """
    Merge objective-specific Instagram analysis results.

    Each objective agent returns an InstagramMetricAnalysis.
    Only non-None fields from the new result are merged so that
    previous objectives are not overwritten.
    """

    if current is None:
        return new_result

    current_data = current.model_dump()
    new_data = new_result.model_dump()

    for field, value in new_data.items():

        # Do not overwrite existing values with None.
        if value is not None:
            current_data[field] = value

    return InstagramMetricAnalysis(**current_data)


def _merge_facebook_result(
    current: FacebookMetricAnalysis | None,
    new_result: FacebookMetricAnalysis,
) -> FacebookMetricAnalysis:
    """
    Merge objective-specific Facebook analysis results.

    Each objective agent returns a FacebookMetricAnalysis.
    Only non-None fields from the new result are merged so that
    previous objectives are not overwritten.
    """

    if current is None:
        return new_result

    current_data = current.model_dump()
    new_data = new_result.model_dump()

    for field, value in new_data.items():

        # Do not overwrite existing values with None.
        if value is not None:
            current_data[field] = value

    return FacebookMetricAnalysis(**current_data)


def meta_runner_node(state: State) -> dict:
    """
    Run all requested objectives sequentially for Instagram and Facebook.

    Example request:

        objectives = [
            "reach",
            "engagement",
            "profilevisit"
        ]

    Execution:

        Instagram Reach
        Facebook Reach

        Instagram Engagement
        Facebook Engagement

        Instagram Profile Visit
        Facebook Profile Visit

    The results are merged so that each objective keeps its own
    objective-specific fields.
    """

    with node("All Meta Ads Running"):

        objectives = _objective_keys(state)

        # ----------------------------------------------------------
        # Agent Mapping
        # ----------------------------------------------------------

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

        # ----------------------------------------------------------
        # Accumulated Results
        # ----------------------------------------------------------

        instagram_result: InstagramMetricAnalysis | None = None
        facebook_result: FacebookMetricAnalysis | None = None

        # ----------------------------------------------------------
        # Run Objectives Sequentially
        # ----------------------------------------------------------

        for objective in objectives:

            # ======================================================
            # Instagram
            # ======================================================

            instagram_agent = instagram_agents.get(objective)

            if instagram_agent is not None:

                # Specific agent only needs state.
                result = instagram_agent(state)

            else:

                # Generic agent needs state + objective.
                result = ig_generic_objective_agent(
                    state,
                    objective,
                )

            if result:

                new_instagram_result = result.get("instagram_result")

                if new_instagram_result is not None:

                    instagram_result = _merge_instagram_result(
                        instagram_result,
                        new_instagram_result,
                    )

            # ======================================================
            # Facebook
            # ======================================================

            facebook_agent = facebook_agents.get(objective)

            if facebook_agent is not None:

                # Specific agent only needs state.
                result = facebook_agent(state)

            else:

                # Generic agent needs state + objective.
                result = fb_generic_objective_agent(
                    state,
                    objective,
                )

            if result:

                new_facebook_result = result.get("facebook_result")

                if new_facebook_result is not None:

                    facebook_result = _merge_facebook_result(
                        facebook_result,
                        new_facebook_result,
                    )

        # ----------------------------------------------------------
        # Build Final Result
        # ----------------------------------------------------------

        final_result = {}

        if instagram_result is not None:
            final_result["instagram_result"] = instagram_result

        if facebook_result is not None:
            final_result["facebook_result"] = facebook_result

        return final_result