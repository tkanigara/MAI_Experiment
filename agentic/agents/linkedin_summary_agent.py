from CentralArch.state import State, SummaryLinkedin
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.linkedin_summary_prompts import SYSTEM_PROMPT
from utils.llm_json import parse_llm_json
import json

def linkedin_summary_agent(state: State) -> dict:
    data ={
        "client_code": state.Metadata.client_code,
        "report_period": state.request.report_date.isoformat() if state.request.report_date else None,
        "linkedin_analysis": state.linkedin_result.model_dump(),
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(data, indent=2, default=str))
    ]

    response = llm.invoke(messages)
    result = parse_llm_json(response.content)


    summary_result = SummaryLinkedin(
        client_code=state.Metadata.client_code,
        key_summary=result.get("key_summary"),
        action_plan=result.get("action_plan"),
    )

    return {
        "summary_linkedin": summary_result
    }