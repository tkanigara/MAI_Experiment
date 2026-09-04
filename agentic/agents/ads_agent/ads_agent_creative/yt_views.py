from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.yt_views import SYSTEM_PROMPTS
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, YoutubeMetricAnalysis


def yt_views_agent(state: State) -> dict:
    with node("Youtube Ads Views Analysis running"):
        return run_ads_analysis_agent(
            state,
            objective="views",
            system_prompt=SYSTEM_PROMPTS,
            result_model=YoutubeMetricAnalysis,
            result_field="youtube_result",
            output_fields=[
                "performance_overview_views",
                "audience_demographics_views",
                "region_breakdown_views",
                "testing_optimization_views",
                "bidding_optimisation_views",
            ],
            label="YouTube Ads Views",
        )
