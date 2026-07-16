from CentralArch.state import State, instagram_result_analysis
from utils.llm_output import get_llm_text
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.ig_analyst_prompt import KPI_PROMPT, SOCMED_OVERVIEW, FOLLOWERS_GROWTH, ENGAGEMENT_PERFORMANCE, INSTAGRAM_ANALYST, SYSTEM_PROMPT
from tools.retrieva_ig_data import retrieve_kpi, retrieve_socmed_overview, retrieve_followers_growth, retrieve_engagement_performance, retrieve_top_performing_content, retrieve_followers_growth_history, retrieve_engagement_performance_history, retrieve_competitor_analysis
from utils.logger import node
from typing import Any
import json
import re
from pprint import pprint
def ig_analysis_agent(state: State) -> State:
    with node("Instagram Agent analysis running"):
    #Kpi 
        kpi_data = retrieve_kpi.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "instagram"

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

        instagram_result = instagram_result_analysis(
            client_code=state.Metadata.client_code,
            client_name=state.Metadata.client_name,
            kpi_analysis=get_llm_text(analysis_result_kpi),
            socmed_overview_analysis=get_llm_text(analysis_result_overview),
            followers_growth_analysis=get_llm_text(analysis_result_foll),
            growth_performance_analysis=get_llm_text(analysis_result_engagement),
        )
    
    
    return {
        "instagram_result": instagram_result
    }

def ig_analysis_agent_2nd(state: State) -> State:
    with node("Instagram analysis running"):

        kpi_data = retrieve_kpi.invoke({
                "client_code": state.Metadata.client_code,
                "report_date": state.request.report_date.isoformat(),
                "platform": "instagram"

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
            "current_period": state.request.report_date.isoformat()
        })

        eng_performance = retrieve_engagement_performance.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat()
        })

        historical_engagement_performance =  retrieve_engagement_performance_history.invoke({
            "client_code": state.Metadata.client_code,
            "current_period": state.request.report_date.isoformat()
        })

        top_content = retrieve_top_performing_content.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "instagram"
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
            "Competitor Analysis": competitor_analysis,
        }
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(data, indent=2, default=str)
            )
        ]

        analysis = llm.invoke(messages)
        print("=" * 80)
        print("INPUT TO LLM")
        pprint(data)
        print("=" * 80)
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
        instagram_result = instagram_result_analysis(
            client_code=state.Metadata.client_code,
            client_name=state.Metadata.client_name,
            kpi_analysis=result["kpi_analysis"],
            socmed_overview_analysis=result["socmed_overview_analysis"],
            followers_growth_analysis=result["followers_growth_analysis"],
            growth_performance_analysis=result["growth_performance_analysis"],
            top_content_performance=(
                result.get("top_content_performance")
                or result.get("top_performance_content")
            ),
            competitor_analysis=result["competitor_analysis"]
        )

    return {
        "instagram_result": instagram_result
    }
