from langgraph.graph import StateGraph, START, END
from agents.report_agent.nodes import reasoning, routing, action
from agents.report_agent.state import ReportState

graph = StateGraph(ReportState)

graph.add_node(
    "reasoning", reasoning
)

graph.add_node(
    "action", action
)

graph.set_entry_point(
    "reasoning"
)

graph.add_conditional_edges(
    "reasoning",
    routing,
    {
        "action":"action",
        "final": END
    }
)

graph.add_edge(
    "action",
    "reasoning"
)

app = graph.compile()