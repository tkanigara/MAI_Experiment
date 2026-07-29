from CentralArch.state import State, SummaryAllSocmed
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.all_socmed_analysis import SYSTEM_PROMPT
from utils.llm_json import parse_llm_json
from tools.retrieva_ig_data import retrieve_instagram_performance
from tools.retrieval_fb_data import retrieve_facebook_performance
from tools.retrieval_tt_data import retrieve_tiktok_performance
from tools.retrieval_yt_data import retrieve_youtube_performance
import json
import re

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



