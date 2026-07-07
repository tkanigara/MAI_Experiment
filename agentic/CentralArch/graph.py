from langgraph.graph import StateGraph, START, END

from .state import State
from agents.supervisor import supervisor_agent
from agents.retrieval import retrieval_agent
from agents.conditional import routing

workflow = StateGraph(State)

workflow.add_node("supervisor", supervisor_agent)
workflow.add_node("retrieval", retrieval_agent)

workflow.add_edge(START, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    routing,
    {
        "retrieval": "retrieval",
        "end": END,
    },
)

workflow.add_edge("retrieval", "supervisor")

app = workflow.compile()