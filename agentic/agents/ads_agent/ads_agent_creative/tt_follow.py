from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import run_ads_analysis_agent
from agentic.prompts.ads_prompts_list.tt_follow import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, TiktokMetricAnalysis


def tt_follow_agent(state: State) -> dict:
    with node("TikTok Ads Follow Analysis running"):
        return run_ads_analysis_agent(
            state,
            system_prompt=SYSTEM_PROMPT,
            result_model=TiktokMetricAnalysis,
            result_field="tiktok_result",
            output_fields=[
                "performance_overview_follow",
                "audience_demographic_follow",
                "region_breakdown_follow",
                "optimisation_follow",
            ],
            label="TikTok Ads Paid Follows",
        )

