from models.huggingface import llm
from graph.state import AgentState
from models.parser import parse_reasoning
from langchain.messages import HumanMessage, SystemMessage
from agents.prompts.tes_prompt import SYSTEM_PROMPT

def user_query(state: AgentState) -> AgentState:
    user_input = state["user_query"]
    user_message = HumanMessage(user_input)
    state["messages"].append(user_message)
    return state

def reasoning(state: AgentState) -> AgentState:
    system_prompt = SYSTEM_PROMPT
    system_message = SystemMessage(system_prompt)
    state["messages"].append(system_message) + state["messages"]

    model_response = llm.invoke(state["messages"])
    reasoning_output = model_response.content
    state["agent_answer"].append(reasoning_output)
    return state

