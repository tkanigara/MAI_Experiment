from langgraph.graph import StateGraph, END
from graph.nodes import user_query ,reasoning    
from graph.state import AgentState

graph = StateGraph(AgentState)

graph.add_node(
    "user_query", user_query
)
graph.add_node(
    "reasoning", reasoning
)

graph.set_entry_point("user_query")
graph.add_edge("user_query", "reasoning")
graph.add_edge("reasoning", END)

app = graph.compile()