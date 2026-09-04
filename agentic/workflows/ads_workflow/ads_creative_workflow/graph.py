from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
# ============================================================
# CORE AGENTS
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.retrieval import retrieval_agent
from agentic.agents.ads_agent.ads_agent_creative.Orchestrator import orchestrator_agent
from agentic.agents.ads_agent.ads_agent_creative.router import router_node
from agentic.agents.ads_agent.ads_agent_creative.summary_agent import summary_agent


# ============================================================
# INSTAGRAM
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.ig_runner_node import (
    instagram_runner_node,
    instagram_router
)

from agentic.agents.ads_agent.ads_agent_creative.ig_engagement_agent import ig_engagement_agent
from agentic.agents.ads_agent.ads_agent_creative.ig_reach_agent import ig_reach_agent
from agentic.agents.ads_agent.ads_agent_creative.ig_profilevisit_agent import ig_profilevisit_agent
from agentic.agents.ads_agent.ads_agent_creative.generic_objective_agents import (
    ig_generic_objective_agent,
    fb_generic_objective_agent,
)
from agentic.agents.ads_agent.ads_agent_creative.meta_runner_node import meta_runner_node


# ============================================================
# FACEBOOK
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.fb_runner_node import (
    facebook_runner_node,
    facebook_router
)

from agentic.agents.ads_agent.ads_agent_creative.fb_engagement_agent import fb_engagement_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_reach_agent import fb_reach_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_profilevisit import fb_profilevisit_agent
from agentic.agents.ads_agent.ads_agent_creative.fb_pagelike_agent import fb_pagelike_agent


# ============================================================
# YOUTUBE
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.yt_runner_node import (
    youtube_runner_node,
    youtube_router
)

from agentic.agents.ads_agent.ads_agent_creative.yt_impressions import yt_impressions_agent
from agentic.agents.ads_agent.ads_agent_creative.yt_views import yt_views_agent


# ============================================================
# TIKTOK
# ============================================================

from agentic.agents.ads_agent.ads_agent_creative.tt_runner_node import (
    tiktok_runner_node,
    tiktok_router
)

from agentic.agents.ads_agent.ads_agent_creative.tt_follow import tt_follow_agent
from agentic.agents.ads_agent.ads_agent_creative.tt_views_agent import tt_views_agent


# ============================================================
# ROUTER → RUNNER DISPATCHER
# ============================================================

def route_to_runner_node(state: State):
    return [
        Send(
            runner_name,
            state
        )
        for runner_name in state.routes
    ]


# ============================================================
# INITIALIZE WORKFLOW
# ============================================================

workflow = StateGraph(State)


# ============================================================
# CORE NODES
# ============================================================

workflow.add_node(
    "retrieval",
    retrieval_agent
)

workflow.add_node(
    "orchestrator",
    orchestrator_agent
)

workflow.add_node(
    "router",
    router_node
)

workflow.add_node(
    "summary",
    summary_agent
)


# ============================================================
# INSTAGRAM NODES
# ============================================================

workflow.add_node(
    "ig_runner_node",
    instagram_runner_node
)

workflow.add_node(
    "instagram_engagement_agent",
    ig_engagement_agent
)

workflow.add_node(
    "instagram_reach_agent",
    ig_reach_agent
)

workflow.add_node(
    "instagram_profilevisit_agent",
    ig_profilevisit_agent
)

workflow.add_node(
    "instagram_generic_objective_agent",
    ig_generic_objective_agent
)

workflow.add_node(
    "meta_runner_node",
    meta_runner_node
)


# ============================================================
# FACEBOOK NODES
# ============================================================

workflow.add_node(
    "fb_runner_node",
    facebook_runner_node
)

workflow.add_node(
    "facebook_engagement_agent",
    fb_engagement_agent
)

workflow.add_node(
    "facebook_reach_agent",
    fb_reach_agent
)

workflow.add_node(
    "facebook_profilevisit_agent",
    fb_profilevisit_agent
)

workflow.add_node(
    "facebook_pagelike_agent",
    fb_pagelike_agent
)

workflow.add_node(
    "facebook_generic_objective_agent",
    fb_generic_objective_agent
)


# ============================================================
# YOUTUBE NODES
# ============================================================

workflow.add_node(
    "yt_runner_node",
    youtube_runner_node
)

workflow.add_node(
    "youtube_impressions_agent",
    yt_impressions_agent
)

workflow.add_node(
    "youtube_views_agent",
    yt_views_agent
)


# ============================================================
# TIKTOK NODES
# ============================================================

workflow.add_node(
    "tt_runner_node",
    tiktok_runner_node
)

workflow.add_node(
    "tiktok_views",
    tt_views_agent
)

workflow.add_node(
    "tiktok_follow",
    tt_follow_agent
)


# ============================================================
# MAIN FLOW
# ============================================================

workflow.add_edge(
    START,
    "retrieval"
)

workflow.add_edge(
    "retrieval",
    "orchestrator"
)

workflow.add_edge(
    "orchestrator",
    "router"
)


# ============================================================
# ROUTER → PLATFORM RUNNERS
# ============================================================

workflow.add_conditional_edges(
    "router",
    route_to_runner_node
)


# ============================================================
# INSTAGRAM RUNNER → INSTAGRAM AGENTS
# ============================================================

workflow.add_edge("ig_runner_node", "summary")


# ============================================================
# FACEBOOK RUNNER → FACEBOOK AGENTS
# ============================================================

workflow.add_edge("fb_runner_node", "summary")


# ============================================================
# YOUTUBE RUNNER → YOUTUBE AGENTS
# ============================================================

workflow.add_edge("yt_runner_node", "summary")


# ============================================================
# TIKTOK RUNNER → TIKTOK AGENTS
# ============================================================

workflow.add_edge("tt_runner_node", "summary")


# ============================================================
# INSTAGRAM AGENTS → SUMMARY
# ============================================================

workflow.add_edge(
    "instagram_engagement_agent",
    "summary"
)

workflow.add_edge(
    "instagram_reach_agent",
    "summary"
)

workflow.add_edge(
    "instagram_profilevisit_agent",
    "summary"
)

workflow.add_edge(
    "instagram_generic_objective_agent",
    "summary"
)

workflow.add_edge(
    "meta_runner_node",
    "summary"
)


# ============================================================
# FACEBOOK AGENTS → SUMMARY
# ============================================================

workflow.add_edge(
    "facebook_engagement_agent",
    "summary"
)

workflow.add_edge(
    "facebook_reach_agent",
    "summary"
)

workflow.add_edge(
    "facebook_profilevisit_agent",
    "summary"
)

workflow.add_edge(
    "facebook_pagelike_agent",
    "summary"
)

workflow.add_edge(
    "facebook_generic_objective_agent",
    "summary"
)


# ============================================================
# YOUTUBE AGENTS → SUMMARY
# ============================================================

workflow.add_edge(
    "youtube_impressions_agent",
    "summary"
)

workflow.add_edge(
    "youtube_views_agent",
    "summary"
)


# ============================================================
# TIKTOK AGENTS → SUMMARY
# ============================================================

workflow.add_edge(
    "tiktok_views",
    "summary"
)

workflow.add_edge(
    "tiktok_follow",
    "summary"
)


# ============================================================
# SUMMARY → END
# ============================================================

workflow.add_edge(
    "summary",
    END
)


# ============================================================
# COMPILE
# ============================================================

creative_architecture = workflow.compile()
