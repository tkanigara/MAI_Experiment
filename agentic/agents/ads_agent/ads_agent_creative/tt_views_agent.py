from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.tt_views import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, TiktokMetricAnalysis


def tt_views_agent(state: State) -> dict:
    with node("TikTok Ads Views Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            result_model=TiktokMetricAnalysis,
            result_field="tiktok_result",
            output_fields=[
                "performance_overview_views",
                "audience_demographic_views",
                "region_breakdown_views",
                "optimisation_views",
            ],
            label="TikTok Ads Views",
        )

