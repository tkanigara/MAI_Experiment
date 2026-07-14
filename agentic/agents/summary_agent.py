from CentralArch.state import State, Summary
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.summary_prompt import SYSTEM_PROMPT
import json


def summary_agent(state: State) -> State:
    data = {
        "client_code": state.Metadata.client_code,
        "report_period": state.request.report_date.isoformat(),
        "Instagram_Analysis": state.instagram_result.model_dump(),
        "Facebook_Analysis": state.facebook_result.model_dump(),
        "Tiktok_Analysis": state.tiktok_result.model_dump(),
        "Youtube_Analysis": state.youtube_result.model_dump()
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(data, indent=2, default=str))
    ]

    response = llm.invoke(messages)
    if isinstance(response.content, list):
        summary_text = response.content[0].get("text", "")
    else:
        summary_text = str(response.content)

    summary_result = Summary(
        client_code=state.Metadata.client_code,
        summary_result=summary_text
    )

    return {
        "summary_result": summary_result
    }