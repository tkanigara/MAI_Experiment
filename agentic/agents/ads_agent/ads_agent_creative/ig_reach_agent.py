import json
from agentic.models.gemini import llm
from langchain_core.messages import SystemMessage, HumanMessage
from agentic.prompts.ads_prompts_list.ig_reach import SYSTEM_PROMPT
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, InstagramMetricAnalysis
from agentic.tools.tools_list_ads_creative.retrieve_ig_data import retrieval_reach_data
from agentic.utils.llm_output import get_llm_text
from agentic.utils.logger import node, console
def ig_reach_agent(state: State):
    with node("Instagram Reach agent"):
        data = retrieval_reach_data.invoke({
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
                "instagram_metric_analysis": InstagramMetricAnalysis(
                    client_code=state.request.client_code,
                    objective="reach",
                    analysis_error=f"Invalid LLM JSON output: {str(e)}",
                )
            }
        instagram_analysis = InstagramMetricAnalysis(
            client_code=state.request.client_code,
            objective="reach",

            performance_overview_reach=(
                analysis_data.get(
                    "performance_overview_reach"
                )
            ),

            content_analysis_reach=(
                analysis_data.get(
                    "content_analysis_reach"
                )
            ),

            placement_analysis_reach=(
                analysis_data.get(
                    "placement_analysis_reach"
                )
            ),

            audience_demographic_analysis_reach=(
                analysis_data.get(
                    "audience_demographic_analysis_reach"
                )
            ),

            region_analysis_reach=(
                analysis_data.get(
                    "region_analysis_reach"
                )
            ),

            optimisation_action_reach=(
                analysis_data.get(
                    "optimisation_action_reach"
                )
            ),
        )

        console.print("[green] Instagram reach analysis result: [/green]")
        console.print(instagram_analysis.model_dump_json(indent=2, exclude_none=True))
        return {
            "instagram_result": instagram_analysis
        }