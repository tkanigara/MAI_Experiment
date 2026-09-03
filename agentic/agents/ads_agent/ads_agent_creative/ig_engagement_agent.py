from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, InstagramMetricAnalysis
from agentic.prompts.ads_prompts_list.ig_engagement import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent

def ig_engagement_agent(state: State) -> dict:
    with node("Instagram Ads Engagement Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            objective="engagement",
            result_model=InstagramMetricAnalysis,
            result_field="instagram_result",
            output_fields=[
                "performance_overview_engagement",
                "content_analysis_engagement",
                "placement_analysis_engagement",
                "audience_demographic_analysis_engagement",
                "region_analysis_engagement",
                "optimisation_action_engagement",
            ],
            label="Instagram Ads Engagement",
        )
