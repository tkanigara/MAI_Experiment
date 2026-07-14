from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from CentralArch.state import State
from agents.retrieval import retrieval_agent
from agents.router import router_node
from agents.ig_analysis_agent import ig_analysis_agent, ig_analysis_agent_2nd
from agents.fb_analysis_agent import fb_analysis_agent, fb_analysis_agent_2nd
from agents.tt_analysis_agent import tt_analysis_agent, tt_analysis_agent_2nd
from agents.yt_analysis_agent import yt_analysis_agent, yt_analysis_agent_2nd
from agents.summary_agent import summary_agent


def route_to_agents(state: State):
    return [
        Send(agent_name, state)
        for agent_name in state.routes
    ]


workflow = StateGraph(State)

workflow.add_node("retrieval", retrieval_agent)
workflow.add_node("router", router_node)

workflow.add_node("ig_analysis_agent", ig_analysis_agent_2nd)
workflow.add_node("fb_analysis_agent", fb_analysis_agent_2nd)
workflow.add_node("tt_analysis_agent", tt_analysis_agent_2nd)
workflow.add_node("yt_analysis_agent", yt_analysis_agent_2nd)

workflow.add_node("summary", summary_agent)


workflow.add_edge(START, "retrieval")
workflow.add_edge("retrieval", "router")
workflow.add_conditional_edges(
    "router",
    route_to_agents
)
workflow.add_edge("ig_analysis_agent", "summary")
workflow.add_edge("fb_analysis_agent", "summary")
workflow.add_edge("tt_analysis_agent", "summary")
workflow.add_edge("yt_analysis_agent", "summary")

workflow.add_edge("summary", END)

app = workflow.compile()