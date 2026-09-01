from workflows.socmed_workflow.state import State, youtube_result_analysis
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.socmed_prompts_list.yt_analyst_prompt import KPI_PROMPT, SOCMED_OVERVIEW, FOLLOWERS_GROWTH, ENGAGEMENT_PERFORMANCE, YOUTUBE_ANALYST, SYSTEM_PROMPT
from tools.tools_list_socmed.retrieval_yt_data import retrieve_kpi, retrieve_socmed_overview, retrieve_followers_growth, retrieve_engagement_performance, retrieve_content_by_bucket,  retrieve_followers_growth_history, retrieve_engagement_performance_history, retrieve_competitor_analysis
from utils.logger import node
from typing import Any
import json
from utils.llm_output import get_llm_text
import re

def yt_analysis_agent(state: State) -> State:
    with node("Youtube Agent analysis running"):
    #Kpi 
        kpi_data = retrieve_kpi.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "youtube"

        })
        KPI = KPI_PROMPT
        messages_kpi = [
            SystemMessage(content=KPI),
            HumanMessage(content=json.dumps(kpi_data, indent=2, default=str))
        ]

        analysis_result_kpi = llm.invoke(messages_kpi)

        #Social Media Overview
        socmed = retrieve_socmed_overview.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        SOCMED_OVERVIEW_PROMPT = SOCMED_OVERVIEW
        messages_overview = [
            SystemMessage(content=SOCMED_OVERVIEW_PROMPT),
            HumanMessage(content=json.dumps(socmed, indent=2, default=str))
        ]

        analysis_result_overview = llm.invoke(messages_overview)

        #Followers_growth
        foll_growth = retrieve_followers_growth.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        FOLL_GROWTH_PROMPT = FOLLOWERS_GROWTH
        messages_foll = [
            SystemMessage(content=FOLL_GROWTH_PROMPT),
            HumanMessage(content=json.dumps(foll_growth, indent=2, default=str))
        ]

        analysis_result_foll = llm.invoke(messages_foll)

        #Engagement_perfomance
        eng_performance = retrieve_engagement_performance.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        ENGAGEMENT_PROMPT = ENGAGEMENT_PERFORMANCE
        messages_engagement = [
            SystemMessage(content=ENGAGEMENT_PROMPT),
            HumanMessage(content=json.dumps(eng_performance, indent=2, default=str))
        ]

        analysis_result_engagement = llm.invoke(messages_engagement)

        youtube_result = youtube_result_analysis(
            client_code=state.Metadata.client_code,
            client_name=state.Metadata.client_name,
            kpi_analysis=get_llm_text(analysis_result_kpi),
            socmed_overview_analysis=get_llm_text(analysis_result_overview),
            followers_growth_analysis=get_llm_text(analysis_result_foll.content),
            growth_performance_analysis=get_llm_text(analysis_result_engagement),
        )
    
    
    return {
        "youtube_result": youtube_result
    }

def yt_analysis_agent_2nd(state: State) -> State:
    with node("Youtube analysis running"):

        kpi_data = retrieve_kpi.invoke({
                "client_code": state.Metadata.client_code,
                "report_date": state.request.report_date.isoformat(),
                "platform": "youtube"

            })
        
        socmed = retrieve_socmed_overview.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        foll_growth = retrieve_followers_growth.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        historical_foll_growth =  retrieve_followers_growth_history.invoke({
            "client_code": state.Metadata.client_code,
            "current_report_period_id": (
                foll_growth.get("report_period_id")
                or state.Metadata.report_period_id
            ),
        })

        eng_performance = retrieve_engagement_performance.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        historical_engagement_performance =  retrieve_engagement_performance_history.invoke({
            "client_code": state.Metadata.client_code,
            "current_report_period_id": (
                eng_performance.get("report_period_id")
                or state.Metadata.report_period_id
            ),
        })

        top_content = retrieve_content_by_bucket.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "youtube",
            "bucket": "top"
        })

        low_content = retrieve_content_by_bucket.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "youtube",
            "bucket": "low"
        })

        competitor_analysis = retrieve_competitor_analysis.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "instagram",
        })
        data = {
            "KPI": kpi_data,
            "Social Media Overview": socmed,

            "Followers Growth": {
                "Current Period": foll_growth,
                "Historical Data": historical_foll_growth,
            },

            "Engagement Performance": {
                "Current Period": eng_performance,
                "Historical Data": historical_engagement_performance,
            },

            "Top Content Performance": top_content,
            "Low Content Performance": low_content,
            "Competitor Analysis": competitor_analysis,
        }
        
        messages = [
            SystemMessage(content=YOUTUBE_ANALYST),
            HumanMessage(
                content=json.dumps(data, indent=2, default=str)
            )
        ]
        analysis = llm.invoke(messages)
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

        # Hapus markdown jika ada
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        # Hapus trailing comma
        text = re.sub(r",(\s*[}\]])", r"\1", text)

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            print("JSON ERROR:", e)
            print(text)
            raise

        youtube_result = youtube_result_analysis(
            client_code=state.Metadata.client_code,
            client_name=state.Metadata.client_name,
            kpi_analysis=result["kpi_analysis"],
            socmed_overview_analysis=result["socmed_overview_analysis"],
            followers_growth_analysis=result["followers_growth_analysis"],
            growth_performance_analysis=result["growth_performance_analysis"],
            top_content_performance=result["top_content_performance"],
            low_content_performance=result["low_content_performance"],
            competitor_analysis=result["competitor_analysis"]
        )

    return {
    "youtube_result": youtube_result
    }





        

    
