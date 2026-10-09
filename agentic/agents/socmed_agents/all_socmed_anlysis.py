from workflows.socmed_workflow.state import State, SummaryAllSocmed
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.socmed_prompts_list.all_socmed_analysis import SYSTEM_PROMPT_2, SYSTEM_PROMPT
from tools.tools_list_socmed.retrieva_ig_data import retrieve_instagram_performance
from tools.tools_list_socmed.retrieval_fb_data import retrieve_facebook_performance
from tools.tools_list_socmed.retrieval_tt_data import retrieve_tiktok_performance
from tools.tools_list_socmed.retrieval_yt_data import retrieve_youtube_performance
from tools.tools_list_socmed.retrieve_ll_data import retrieve_linkedin_performance
from langchain.agents import create_agent
import json
import re
from utils.llm_output import get_llm_text

def all_socmed_performance_agent_2nd(state):
    agent = create_agent(
        model=llm,
        tools=[
            retrieve_instagram_performance,
            retrieve_facebook_performance,
            retrieve_tiktok_performance,
            retrieve_youtube_performance,
            retrieve_linkedin_performance,
        ],
        system_prompt=SystemMessage(content=SYSTEM_PROMPT_2),
    )

    metadata = state.Metadata
    payload = metadata.model_dump(mode="json")
    response = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=json.dumps(
                        payload,
                        indent=2
                    )
                )
            ]
        }
    )
    final_message = response["messages"][-1]
    text = get_llm_text(final_message)
    result = json.loads(text)
    state.summary_all_socmed = SummaryAllSocmed(
        client_code=metadata.client_code,
        summary=result["summary"],
    )
    return state

def all_socmed_performance_agent(state: State) -> State:

    instagram_data = retrieve_instagram_performance.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    facebook_data = retrieve_facebook_performance.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    tiktok_data = retrieve_tiktok_performance.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    youtube_data = retrieve_youtube_performance.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    data = {
        "instagram_data": instagram_data,
        "facebook_data": facebook_data,
        "tiktok_data": tiktok_data,
        "youtube_data": youtube_data,
    }

    message = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(data, indent=2, default=str))
    ]

    analysis = llm.invoke(message)
    content = analysis.content

    if isinstance(content, list):
        text = "".join(
            part["text"]
            for part in content
            if part.get("type") == "text"
        )
    else:
        text = content
    text = text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        print("JSON ERROR:", e)
        print(text)
        raise

    all_socmed_analysis = SummaryAllSocmed(
        client_code=state.Metadata.client_code,
        summary=result["summary"]
    )

    return {
        "summary_all_socmed": all_socmed_analysis
    }



