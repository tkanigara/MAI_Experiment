from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, InstagramMetricAnalysis
from agentic.prompts.ads_prompts_list.ig_reach import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent

def ig_reach_agent(state: State) -> dict:
    with node("Instagram Ads Reach Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            result_model=InstagramMetricAnalysis,
            result_field="instagram_result",
            output_fields=[
                "performance_overview_reach",
                "content_analysis_reach",
                "placement_analysis_reach",
                "audience_demographic_analysis_reach",
                "region_analysis_reach",
                "optimisation_action_reach",
            ],
            label="Instagram Ads Reach",
        )
