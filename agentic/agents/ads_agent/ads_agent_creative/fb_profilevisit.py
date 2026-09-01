from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.fb_profile import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    FacebookMetricAnalysis,
    State,
)


def fb_profilevisit_agent(state: State) -> dict:
    with node("Facebook Ads Profile Visit Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            result_model=FacebookMetricAnalysis,
            result_field="facebook_result",
            output_fields=[
                "performance_overview_profilevisit",
                "content_analysis_profilevisit",
                "placement_analysis_profilevisit",
                "audience_demographic_analysis_profilevisit",
                "region_analysis_profilevisit",
                "optimisation_action_profilevisit",
            ],
            label="Facebook Ads Profile Visits",
        )

