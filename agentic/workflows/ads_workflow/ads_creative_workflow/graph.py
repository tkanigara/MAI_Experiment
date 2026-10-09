from langgraph.graph import StateGraph, START, END
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State


# ============================================================
# CORE AGENTS
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.retrieval import (
    retrieval_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.Orchestrator import (
    orchestrator_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.router import (
    router_node,
)

from agentic.agents.ads_agent.ads_agent_creative.summary_agent import (
    summary_agent,
)


# ============================================================
# INSTAGRAM AGENTS
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import (
    ig_reach_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.ig_engagement_agent import (
    ig_engagement_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.ig_profilevisit_agent import (
    ig_profilevisit_agent,
)


# ============================================================
# FACEBOOK AGENTS
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.fb_reach_agent import (
    fb_reach_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.fb_engagement_agent import (
    fb_engagement_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.fb_profilevisit import (
    fb_profilevisit_agent,
)

from agentic.agents.ads_agent.ads_agent_creative.fb_pagelike_agent import (
    fb_pagelike_agent,
)


# ============================================================
# YOUTUBE AGENTS
# ============================================================

# Aktifkan import ini ketika agent YouTube sudah tersedia.
#
# from agentic.agents.ads_agent.ads_agent_creative.yt_impressions_agent import (
#     yt_impressions_agent,
# )
#
# from agentic.agents.ads_agent.ads_agent_creative.yt_views_agent import (
#     yt_views_agent,
# )


# ============================================================
# TIKTOK AGENTS
# ============================================================

# Aktifkan import ini ketika agent TikTok sudah tersedia.
#
# from agentic.agents.ads_agent.ads_agent_creative.tt_views_agent import (
#     tt_views_agent,
# )
#
# from agentic.agents.ads_agent.ads_agent_creative.tt_follow_agent import (
#     tt_follow_agent,
# )


# ============================================================
# INSTAGRAM RUNNER
# ============================================================

def instagram_runner_node(state: State):

    objectives = [
        objective.lower().strip()
        for objective in state.request.objectives
    ]

    current_state = state

    for objective in objectives:

        if objective == "reach":

            result = ig_reach_agent(current_state)

        elif objective == "engagement":

            result = ig_engagement_agent(current_state)

        elif objective == "profilevisit":

            result = ig_profilevisit_agent(current_state)

        else:
            continue

        if result:

            current_state = current_state.model_copy(
                update=result
            )

    # ========================================================
    # IMPORTANT
    # Jangan return seluruh State.
    #
    # Karena Instagram dan Facebook dapat berjalan
    # secara paralel.
    # ========================================================

    return {
        "instagram_result": current_state.instagram_result
    }


# ============================================================
# FACEBOOK RUNNER
# ============================================================

def facebook_runner_node(state: State):

    objectives = [
        objective.lower().strip()
        for objective in state.request.objectives
    ]

    current_state = state

    for objective in objectives:

        if objective == "reach":

            result = fb_reach_agent(current_state)

        elif objective == "engagement":

            result = fb_engagement_agent(current_state)

        elif objective == "profilevisit":

            result = fb_profilevisit_agent(current_state)

        elif objective == "pagelike":

            result = fb_pagelike_agent(current_state)

        else:
            continue

        if result:

            current_state = current_state.model_copy(
                update=result
            )

    # ========================================================
    # IMPORTANT
    # Hanya return hasil Facebook.
    # ========================================================

    return {
        "facebook_result": current_state.facebook_result
    }


# ============================================================
# YOUTUBE RUNNER
# ============================================================

def youtube_runner_node(state: State):

    objectives = [
        objective.lower().strip()
        for objective in state.request.objectives
    ]

    current_state = state

    for objective in objectives:

        if objective == "impressions":

            result = yt_impressions_agent(current_state)

        elif objective == "views":

            result = yt_views_agent(current_state)

        else:
            continue

        if result:

            current_state = current_state.model_copy(
                update=result
            )

    return {
        "youtube_result": current_state.youtube_result
    }


# ============================================================
# TIKTOK RUNNER
# ============================================================

def tiktok_runner_node(state: State):

    objectives = [
        objective.lower().strip()
        for objective in state.request.objectives
    ]

    current_state = state

    for objective in objectives:

        if objective == "views":

            result = tt_views_agent(current_state)

        elif objective == "follow":

            result = tt_follow_agent(current_state)

        else:
            continue

        if result:

            current_state = current_state.model_copy(
                update=result
            )

    return {
        "tiktok_result": current_state.tiktok_result
    }


# ============================================================
# PLATFORM ROUTER
# ============================================================

def route_platform(state: State):

    return state.routes


# ============================================================
# GRAPH
# ============================================================

workflow = StateGraph(State)


# ============================================================
# CORE NODES
# ============================================================

workflow.add_node(
    "retrieval",
    retrieval_agent,
)

workflow.add_node(
    "orchestrator",
    orchestrator_agent,
)

workflow.add_node(
    "router",
    router_node,
)


# ============================================================
# PLATFORM RUNNERS
# ============================================================

workflow.add_node(
    "instagram_runner",
    instagram_runner_node,
)

workflow.add_node(
    "facebook_runner",
    facebook_runner_node,
)

workflow.add_node(
    "youtube_runner",
    youtube_runner_node,
)

workflow.add_node(
    "tiktok_runner",
    tiktok_runner_node,
)


# ============================================================
# SUMMARY
# ============================================================

workflow.add_node(
    "summary",
    summary_agent,
)


# ============================================================
# START → RETRIEVAL
# ============================================================

workflow.add_edge(
    START,
    "retrieval",
)


# ============================================================
# RETRIEVAL → ORCHESTRATOR
# ============================================================

workflow.add_edge(
    "retrieval",
    "orchestrator",
)


# ============================================================
# ORCHESTRATOR → ROUTER
# ============================================================

workflow.add_edge(
    "orchestrator",
    "router",
)


# ============================================================
# ROUTER → PLATFORM
# ============================================================

workflow.add_conditional_edges(
    "router",
    route_platform,
    {
        "instagram_runner": "instagram_runner",
        "facebook_runner": "facebook_runner",
        "youtube_runner": "youtube_runner",
        "tiktok_runner": "tiktok_runner",
    },
)


# ============================================================
# PLATFORM → SUMMARY
# ============================================================

workflow.add_edge(
    "instagram_runner",
    "summary",
)

workflow.add_edge(
    "facebook_runner",
    "summary",
)

workflow.add_edge(
    "youtube_runner",
    "summary",
)

workflow.add_edge(
    "tiktok_runner",
    "summary",
)


# ============================================================
# SUMMARY → END
# ============================================================

workflow.add_edge(
    "summary",
    END,
)


# ============================================================
# COMPILE
# ============================================================

creative_architecture = workflow.compile()
