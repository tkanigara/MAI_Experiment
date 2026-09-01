from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.fb_reach import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    FacebookMetricAnalysis,
    State,
)


def fb_reach_agent(state: State) -> dict:
    with node("Facebook Ads Reach Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            result_model=FacebookMetricAnalysis,
            result_field="facebook_result",
            output_fields=[
                "performance_overview_reach",
                "content_analysis_reach",
                "placement_analysis_reach",
                "audience_demographic_analysis_reach",
                "region_analysis_reach",
                "optimisation_action_reach",
            ],
            label="Facebook Ads Reach",
        )

