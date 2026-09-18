import json
from langchain_core.messages import SystemMessage, HumanMessage
from agentic.models.gemini import llm
from agentic.prompts.ads_prompts_list.summary import SYSTEM_PROMPT
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, SummaryAll
from agentic.utils.llm_output import get_llm_text


def summary_agent(state: State):

    analysis_data = {
        "instagram": state.instagram_result.model_dump(),
        "facebook": state.facebook_result.model_dump(),
        "tiktok": state.tiktok_result.model_dump(),
        "youtube": state.youtube_result.model_dump(),
    }

    messages = [
        SystemMessage(
            content=SYSTEM_PROMPT
        ),
        HumanMessage(
            content=json.dumps(
                analysis_data,
                indent=2,
                default=str,
            )
        ),
    ]

    response = llm.invoke(messages)
    result = get_llm_text(response)

    try:
        summary_data = json.loads(result)

    except json.JSONDecodeError as e:

        return {
            "summary_result": SummaryAll(
                client_code=state.request.client_code,
                summary_result=None,
            ),
        }

    summary = SummaryAll(
        client_code=state.request.client_code,
        summary_result=summary_data.get(
            "summary_result"
        ),
    )

    return {
        "summary_result": summary,
    }