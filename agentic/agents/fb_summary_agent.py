from CentralArch.state import State, SummaryFacebook
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.fb_summary_prompts import SYSTEM_PROMPT
import json


def fb_summary_agent(state: State) -> State:
    data = {
        "client_code": state.Metadata.client_code,
        "report_period": state.request.report_date.isoformat(),
        "facebook_analysis": state.tiktok_result.model_dump(),
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(data, indent=2, default=str))
    ]

    response = llm.invoke(messages)

    if isinstance(response.content, list):
        content = response.content[0].get("text", "")
    else:
        content = str(response.content)

    result = json.loads(content)

    summary_result = SummaryFacebook(
        client_code=state.Metadata.client_code,
        key_summary=result.get("key_summary"),
        action_plan=result.get("action_plan"),
    )

    return {
        "fb_summary_result": summary_result
    }