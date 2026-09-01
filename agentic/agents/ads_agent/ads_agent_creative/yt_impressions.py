from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.yt_impressions import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, YoutubeMetricAnalysis


def yt_impressions_agent(state: State) -> dict:
    with node("Youtube Ads Impressions Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            result_model=YoutubeMetricAnalysis,
            result_field="youtube_result",
            output_fields=[
                "performance_overview_impressions",
                "audience_demographics_impressions",
                "region_breakdown_impressions",
                "testing_optimization_impressions",
                "bidding_optimisation_impressions",
            ],
            label="YouTube Ads Impressions",
        )

