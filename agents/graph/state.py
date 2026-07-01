from typing_extensions import TypeDict

class AgentState(TypeDict):
    messages: list[dict]
    user_query: str
    agent_answer: str

    
