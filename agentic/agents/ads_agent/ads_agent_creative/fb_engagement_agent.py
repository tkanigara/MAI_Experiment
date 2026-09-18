import json
from agentic.models.gemini import llm
from langchain_core.messages import SystemMessage, HumanMessage
from agentic.prompts.ads_prompts_list.fb_engagement import SYSTEM_PROMPT
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, FacebookMetricAnalysis
from agentic.tools.tools_list_ads_creative.retrieve_fb_data import retrieval_engagement_data
from agentic.utils.llm_output import get_llm_text
from agentic.utils.logger import node, console

def fb_engagement_agent(state: State):
    with node("Facebook Engagement Agent"):
        data = retrieval_engagement_data.invoke({
            "client_code": state.request.client_code,
            "period_id": state.request.period_id,
            "campaign_ids": state.request.campaign_ids,
        })

        messages = [
            SystemMessage(
                content=SYSTEM_PROMPT
            ),
            HumanMessage(
                content=json.dumps(
                    data,
                    indent=2,
                    default=str,
                )
            ),
        ]

        analysis = llm.invoke(messages)
        result = get_llm_text(analysis)

        try:
            analysis_data = json.loads(result)

        except json.JSONDecodeError as e:
            return {
                "facebook_metric_analysis": FacebookMetricAnalysis(
                    client_code=state.request.client_code,
                    objective="engagement",
                    analysis_error=f"Invalid LLM JSON output: {str(e)}",
                )
            }
        facebook_analysis = FacebookMetricAnalysis(
            client_code=state.request.client_code,
            objective="engagement",

            performance_overview_engagement=(
                analysis_data.get(
                    "performance_overview_engagement"
                )
            ),

            content_analysis_engagement=(
                analysis_data.get(
                    "content_analysis_engagement"
                )
            ),

            placement_analysis_engagement=(
                analysis_data.get(
                    "placement_analysis_engagement"
                )
            ),

            audience_demographic_analysis_engagement=(
                analysis_data.get(
                    "audience_demographic_analysis_engagement"
                )
            ),

            region_analysis_engagement=(
                analysis_data.get(
                    "region_analysis_engagement"
                )
            ),

            optimisation_action_engagement=(
                analysis_data.get(
                    "optimisation_action_engagement"
                )
            ),
        )

        console.print("[green] Facebook Engagement Analysis Result: [/green]")
        console.print(facebook_analysis.model_dump_json(indent=2, exclude_none=True))
        
        return {
            "facebook_result": facebook_analysis
        }