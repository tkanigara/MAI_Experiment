"""Generic objective agents for canonical Ads objectives."""

from agentic.agents.ads_agent.ads_agent_creative.analysis_helpers import (
    run_ads_analysis_agent,
)
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    FacebookMetricAnalysis,
    InstagramMetricAnalysis,
    State,
)


_FIELDS = [
    "performance_overview",
    "content_analysis",
    "placement_analysis",
    "audience_demographic_analysis",
    "region_analysis",
    "optimisation_action",
]


def ig_generic_objective_agent(state: State) -> dict:
    return run_ads_analysis_agent(
        state,
        system_prompt=None,
        result_model=InstagramMetricAnalysis,
        result_field="instagram_result",
        output_fields=_FIELDS,
        label=f"Instagram Ads {state.request.objective}",
    )


def fb_generic_objective_agent(state: State) -> dict:
    return run_ads_analysis_agent(
        state,
        system_prompt=None,
        result_model=FacebookMetricAnalysis,
        result_field="facebook_result",
        output_fields=_FIELDS,
        label=f"Facebook Ads {state.request.objective}",
    )

