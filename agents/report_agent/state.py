from typing_extensions import TypedDict, List

class ReportState(TypedDict):
    messages: List[dict]
    
    user_query: str

    thought: str

    action: str

    action_input: str

    observation: str

    final_answer: str
