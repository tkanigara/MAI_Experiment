from CentralArch.state import State, SummaryTiktok
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.tt_summary_prompt import SYSTEM_PROMPT
import json


def tt_summary_agent(state: State) -> State:
    data = {
        "client_code": state.Metadata.client_code,
        "report_period": state.request.report_date.isoformat(),
        "tiktok_analysis": state.tiktok_result.model_dump(),
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

    summary_result = SummaryTiktok(
        client_code=state.Metadata.client_code,
        key_summary=result.get("key_summary"),
        action_plan=result.get("action_plan"),
    )

    return {
        "tiktok_summary_result": summary_result
    }