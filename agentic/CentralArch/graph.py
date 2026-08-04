from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from CentralArch.state import State
from agents.retrieval import retrieval_agent
from agents.router import router_node
from agents.ig_analysis_agent import ig_analysis_agent, ig_analysis_agent_2nd
from agents.fb_analysis_agent import fb_analysis_agent, fb_analysis_agent_2nd
from agents.tt_analysis_agent import tt_analysis_agent, tt_analysis_agent_2nd
from agents.yt_analysis_agent import yt_analysis_agent, yt_analysis_agent_2nd
from agents.ig_summary_agent import ig_summary_agent
from agents.fb_summary_agent import fb_summary_agent
from agents.tt_summary_agent import tt_summary_agent
from agents.yt_summary_agent import yt_summary_agent
from agents.persist_insights import persist_insights_node
from agents.slides_generation import slides_generation_node
from agents.cached_insights import cached_insights_node
from agents.all_socmed_anlysis import all_socmed_performance_agent_2nd

def route_to_agents(state: State):
    return [
        Send(agent_name, state)
        for agent_name in state.routes
    ]


def route_after_persistence(state: State):
    return "generate_slides" if state.request.generate_slides else END


def route_after_cache(state: State):
    if not state.analysis_cache_hit:
        return "router"
    return "generate_slides" if state.request.generate_slides else END


workflow = StateGraph(State)

workflow.add_node("retrieval", retrieval_agent)
workflow.add_node("router", router_node)
workflow.add_node("cached_insights", cached_insights_node)

workflow.add_node("ig_analysis_agent", ig_analysis_agent_2nd)
workflow.add_node("fb_analysis_agent", fb_analysis_agent_2nd)
workflow.add_node("tt_analysis_agent", tt_analysis_agent_2nd)
workflow.add_node("yt_analysis_agent", yt_analysis_agent_2nd)

workflow.add_node("all_socmed_performance", all_socmed_performance_agent_2nd)
workflow.add_node("ig_summary_agent", ig_summary_agent)
workflow.add_node("fb_summary_agent", fb_summary_agent)
workflow.add_node("tt_summary_agent", tt_summary_agent)
workflow.add_node("yt_summary_agent", yt_summary_agent)
workflow.add_node("persist_insights", persist_insights_node)
workflow.add_node("generate_slides", slides_generation_node)

# Entry
workflow.add_edge(START, "retrieval")
workflow.add_edge("retrieval", "cached_insights")
workflow.add_conditional_edges("cached_insights", route_after_cache)

# Router -> Analysis
workflow.add_conditional_edges(
    "router",
    route_to_agents
)

# Analysis -> Summary
workflow.add_edge("ig_analysis_agent", "ig_summary_agent")
workflow.add_edge("fb_analysis_agent", "fb_summary_agent")
workflow.add_edge("tt_analysis_agent", "tt_summary_agent")
workflow.add_edge("yt_analysis_agent", "yt_summary_agent")

# Summary -> END
workflow.add_edge("ig_summary_agent", "all_socmed_performance")
workflow.add_edge("fb_summary_agent", "all_socmed_performance")
workflow.add_edge("tt_summary_agent", "all_socmed_performance")
workflow.add_edge("yt_summary_agent", "all_socmed_performance")
workflow.add_edge("all_socmed_performance", "persist_insights")
workflow.add_conditional_edges("persist_insights", route_after_persistence)
workflow.add_edge("generate_slides", END)

app = workflow.compile()
