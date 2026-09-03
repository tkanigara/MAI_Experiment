from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.fb_pagelike import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    FacebookMetricAnalysis,
    State,
)


def fb_pagelike_agent(state: State) -> dict:
    with node("Facebook Ads Page Like Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            objective="pagelike",
            result_model=FacebookMetricAnalysis,
            result_field="facebook_result",
            output_fields=[
                "performance_overview_pagelike",
                "content_analysis_pagelike",
                "placement_analysis_pagelike",
                "audience_demographic_analysis_pagelike",
                "region_analysis_pagelike",
                "optimisation_action_pagelike",
            ],
            label="Facebook Ads Page Likes",
        )

