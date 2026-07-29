from models.huggingface import llm
from graph.state import AgentState
from langchain.messages import HumanMessage, SystemMessage
from prompts.tes_prompt import SYSTEM_PROMPT

def user_query(state: AgentState) -> AgentState:
    user_input = state["user_query"]
    user_message = HumanMessage(user_input)
    state["messages"].append(user_message)
    return state

def reasoning(state: AgentState) -> AgentState:
    messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]

    model_response = llm.invoke(messages)
    reasoning_output = model_response.content
    state["agent_answer"].append(reasoning_output)
    state["messages"].append(model_response)
    return state

