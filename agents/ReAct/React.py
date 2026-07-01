from langgraph.graph import StateGraph, END
from graph.nodes import user_query ,reasoning    
from graph.state import AgentState

graph = StateGraph()

graph.add_node(
    "user_query", user_query
)
graph.add_node(
    "reasoning", reasoning
)

app = graph.compile()