import json
from agentic.models.gemini import llm
from langchain_core.messages import SystemMessage, HumanMessage
from agentic.prompts.ads_prompts_list.ig_profile import SYSTEM_PROMPT
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, InstagramMetricAnalysis
from agentic.tools.tools_list_ads_creative.retrieve_ig_data import retrieval_profilevisit_data
from agentic.utils.llm_output import get_llm_text
from agentic.utils.logger import node, console

def ig_profilevisit_agent(state: State):
    with node("Instagram Profile Visit agent"):
        data = retrieval_profilevisit_data.invoke({
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
                    objective="profilevisit",
                    analysis_error=f"Invalid LLM JSON output: {str(e)}",
                )
            }
        instagram_analysis = InstagramMetricAnalysis(
            client_code=state.request.client_code,
            objective="profilevisit",

            performance_overview_profilevisit=(
                analysis_data.get(
                    "performance_overview_profilevisit"
                )
            ),

            content_analysis_profilevisit=(
                analysis_data.get(
                    "content_analysis_profilevisit"
                )
            ),

            placement_analysis_profilevisit=(
                analysis_data.get(
                    "placement_analysis_profilevisit"
                )
            ),

            audience_demographic_analysis_profilevisit=(
                analysis_data.get(
                    "audience_demographic_analysis_profilevisit"
                )
            ),

            region_analysis_profilevisit=(
                analysis_data.get(
                    "region_analysis_profilevisit"
                )
            ),

            optimisation_action_profilevisit=(
                analysis_data.get(
                    "optimisation_action_profilevisit"
                )
            ),
        )

        console.print("[green] Instagram Profile visit analysis result: [/green]")
        console.print(instagram_analysis.model_dump_json(indent=2, exclude_none=True))
        return {
            "instagram_result": instagram_analysis
        }