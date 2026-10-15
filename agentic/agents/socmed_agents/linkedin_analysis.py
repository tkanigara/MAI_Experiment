from workflows.socmed_workflow.state import State, linkedin_result_analysis
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.socmed_prompts_list.linkedin_analysis_prompt import SYSTEM_PROMPT
from tools.tools_list_socmed.retrieve_ll_data import retrieve_kpi, retrieve_socmed_overview, retrieve_followers_growth, retrieve_engagement_performance, retrieve_content_by_bucket,retrieve_followers_growth_history, retrieve_engagement_performance_history, retrieve_competitor_analysis
from utils.llm_json import parse_llm_json
import json

def linkedin_analysis_agent(state: State) -> State:

    kpi_data = retrieve_kpi.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat(),
        "platform": "linkedin"
    })

    socmed = retrieve_socmed_overview.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    foll_growth = retrieve_followers_growth.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    current_period_id = foll_growth.get("report_period_id") or state.Metadata.report_period_id
    history_foll_growth = retrieve_followers_growth_history.invoke({
        "client_code": state.Metadata.client_code,
        "current_report_period_id": current_period_id,
    })

    eng_performance = retrieve_engagement_performance.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat()
    })

    history_eng_performance = retrieve_engagement_performance_history.invoke({
        "client_code": state.Metadata.client_code,
        "current_report_period_id": eng_performance.get("report_period_id") or current_period_id,
    })

    top_content = retrieve_content_by_bucket.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "linkedin",
            "bucket": "top"
    })

    low_content = retrieve_content_by_bucket.invoke({
            "client_code": state.Metadata.client_code,
            "report_date": state.request.report_date.isoformat(),
            "platform": "linkedin",
            "bucket": "low"
    })

    competitor_analysis = retrieve_competitor_analysis.invoke({
        "client_code": state.Metadata.client_code,
        "report_date": state.request.report_date.isoformat(),
        "platform": "linkedin"
    })

    data = {
            "KPI": kpi_data,
            "Social Media Overview": socmed,

            "Followers Growth": {
                "Current Period": foll_growth,
                "Historical Data": history_foll_growth,
            },

            "Engagement Performance": {
                "Current Period": eng_performance,
                "Historical Data": history_eng_performance,
            },

            "Top Content Performance": top_content,
            "Low Content Performance": low_content,
            "Competitor Analysis": competitor_analysis,
        }

    messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(data, indent=2, default=str)
            )
    ]

    analysis = llm.invoke(messages)
    result = parse_llm_json(analysis.content)

    linkedin_result = linkedin_result_analysis(
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
        "linkedin_result": linkedin_result
    }
