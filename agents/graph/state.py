from typing_extensions import TypedDict

class AgentState(TypedDict):
    messages: list[dict]
    user_query: str
    agent_answer: str

    
    
