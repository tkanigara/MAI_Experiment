from agentic.agents.ads_agent.router import router

from agentic.workflows.ads_workflow.ads_creative_workflow.graph import (
    creative_architecture,
)

from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    Request as CreativeRequest,
    State as CreativeState,
)


request = {
    "client_code": "bourbon",
    "period_id": "2026-07-01",
    "analysis_type": "creative",
    "platform_scope": "meta",
    "objectives": [
        "reach",
        "engagement",
        "profilevisit",
        "pagelike",
    ],
    "campaign_ids": [],
    "adset_ids": [],
    "include_breakdowns": True,
}


# =========================================================
# INSTAGRAM RESULT
# =========================================================

def print_instagram_result(result):

    print("\n" + "=" * 80)
    print("INSTAGRAM ANALYSIS")
    print("=" * 80)

    # ---------------------------------------------------------
    # REACH
    # ---------------------------------------------------------

    print("\n### REACH")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_reach)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_reach)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_reach)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_reach)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_reach)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_reach)

    # ---------------------------------------------------------
    # ENGAGEMENT
    # ---------------------------------------------------------

    print("\n### ENGAGEMENT")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_engagement)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_engagement)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_engagement)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_engagement)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_engagement)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_engagement)

    # ---------------------------------------------------------
    # PROFILE VISIT
    # ---------------------------------------------------------

    print("\n### PROFILE VISIT")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_profilevisit)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_profilevisit)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_profilevisit)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_profilevisit)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_profilevisit)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_profilevisit)


# =========================================================
# FACEBOOK RESULT
# =========================================================

def print_facebook_result(result):

    print("\n" + "=" * 80)
    print("FACEBOOK ANALYSIS")
    print("=" * 80)

    # ---------------------------------------------------------
    # GENERIC
    # ---------------------------------------------------------

    print("\n### GENERIC")

    print(
        f"Performance Overview : "
        f"{result.performance_overview}"
    )

    print(
        f"Content Analysis     : "
        f"{result.content_analysis}"
    )

    print(
        f"Placement Analysis   : "
        f"{result.placement_analysis}"
    )

    print(
        f"Audience Demographic : "
        f"{result.audience_demographic_analysis}"
    )

    print(
        f"Region Analysis      : "
        f"{result.region_analysis}"
    )

    print(
        f"Optimisation Action  : "
        f"{result.optimisation_action}"
    )

    # ---------------------------------------------------------
    # REACH
    # ---------------------------------------------------------

    print("\n### REACH")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_reach)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_reach)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_reach)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_reach)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_reach)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_reach)

    # ---------------------------------------------------------
    # ENGAGEMENT
    # ---------------------------------------------------------

    print("\n### ENGAGEMENT")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_engagement)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_engagement)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_engagement)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_engagement)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_engagement)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_engagement)

    # ---------------------------------------------------------
    # PROFILE VISIT
    # ---------------------------------------------------------

    print("\n### PROFILE VISIT")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_profilevisit)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_profilevisit)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_profilevisit)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_profilevisit)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_profilevisit)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_profilevisit)

    # ---------------------------------------------------------
    # PAGE LIKE
    # ---------------------------------------------------------

    print("\n### PAGE LIKE")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_pagelike)

    print("\n--- Content Analysis ---")
    print(result.content_analysis_pagelike)

    print("\n--- Placement Analysis ---")
    print(result.placement_analysis_pagelike)

    print("\n--- Audience Demographic Analysis ---")
    print(result.audience_demographic_analysis_pagelike)

    print("\n--- Region Analysis ---")
    print(result.region_analysis_pagelike)

    print("\n--- Optimisation Action ---")
    print(result.optimisation_action_pagelike)


# =========================================================
# YOUTUBE RESULT
# =========================================================

def print_youtube_result(result):

    print("\n" + "=" * 80)
    print("YOUTUBE ANALYSIS")
    print("=" * 80)

    # ---------------------------------------------------------
    # IMPRESSIONS
    # ---------------------------------------------------------

    print("\n### IMPRESSIONS")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_impressions)

    print("\n--- Audience Demographics ---")
    print(result.audience_demographics_impressions)

    print("\n--- Region Breakdown ---")
    print(result.region_breakdown_impressions)

    print("\n--- Testing Optimization ---")
    print(result.testing_optimization_impressions)

    print("\n--- Bidding Optimisation ---")
    print(result.bidding_optimisation_impressions)

    # ---------------------------------------------------------
    # VIEWS
    # ---------------------------------------------------------

    print("\n### VIEWS")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_views)

    print("\n--- Audience Demographics ---")
    print(result.audience_demographics_views)

    print("\n--- Region Breakdown ---")
    print(result.region_breakdown_views)

    print("\n--- Testing Optimization ---")
    print(result.testing_optimization_views)

    print("\n--- Bidding Optimisation ---")
    print(result.bidding_optimisation_views)


# =========================================================
# TIKTOK RESULT
# =========================================================

def print_tiktok_result(result):

    print("\n" + "=" * 80)
    print("TIKTOK ANALYSIS")
    print("=" * 80)

    # ---------------------------------------------------------
    # VIEWS
    # ---------------------------------------------------------

    print("\n### VIEWS")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_views)

    print("\n--- Audience Demographic ---")
    print(result.audience_demographic_views)

    print("\n--- Region Breakdown ---")
    print(result.region_breakdown_views)

    print("\n--- Optimisation ---")
    print(result.optimisation_views)

    # ---------------------------------------------------------
    # FOLLOW
    # ---------------------------------------------------------

    print("\n### FOLLOW")

    print("\n--- Performance Overview ---")
    print(result.performance_overview_follow)

    print("\n--- Audience Demographic ---")
    print(result.audience_demographic_follow)

    print("\n--- Region Breakdown ---")
    print(result.region_breakdown_follow)

    print("\n--- Optimisation ---")
    print(result.optimisation_follow)


# =========================================================
# RUN WORKFLOW
# =========================================================

def run(request_data: dict):

    # =========================================================
    # ROUTER
    # =========================================================

    route = router(request_data)

    print(f"\n[DEBUG] Route: {route}")

    if route != "creative":
        print(f"[ERROR] Unsupported route: {route}")
        return None

    # =========================================================
    # INITIAL STATE
    # =========================================================

    workflow_request = CreativeRequest(
        **request_data
    )

    initial_state = CreativeState(
        request=workflow_request
    )

    # =========================================================
    # RUN WORKFLOW
    # =========================================================

    result = creative_architecture.invoke(
        initial_state
    )

    result_state = CreativeState.model_validate(
        result
    )

    # =========================================================
    # METADATA
    # =========================================================

    print("\n" + "=" * 80)
    print("METADATA")
    print("=" * 80)

    print(
        f"Client      : "
        f"{result_state.Metadata.client_name}"
    )

    print(
        f"Client Code : "
        f"{result_state.Metadata.client_code}"
    )

    print(
        f"Instagram   : "
        f"{result_state.Metadata.instagram}"
    )

    print(
        f"Facebook    : "
        f"{result_state.Metadata.facebook}"
    )

    print(
        f"TikTok      : "
        f"{result_state.Metadata.tiktok}"
    )

    print(
        f"YouTube     : "
        f"{result_state.Metadata.youtube}"
    )

    # =========================================================
    # ADS DATA
    # =========================================================

    print("\n" + "=" * 80)
    print("ADS DATA")
    print("=" * 80)

    print(
        f"Status      : "
        f"{result_state.ads_data.status}"
    )

    print(
        f"Success     : "
        f"{result_state.ads_data.success}"
    )

    print(
        f"Objectives  : "
        f"{result_state.ads_data.objectives}"
    )

    print(
        f"Platform    : "
        f"{result_state.ads_data.platform_scope}"
    )

    # ---------------------------------------------------------
    # Objective Status
    # ---------------------------------------------------------

    print("\nObjective Status:")

    for objective, data in (
        result_state.ads_data.objective_data.items()
    ):

        print(
            f"  - {objective}: "
            f"{data.get('status', 'unknown')}"
        )

    # =========================================================
    # INSTAGRAM
    # =========================================================

    if result_state.Metadata.instagram:

        print_instagram_result(
            result_state.instagram_result
        )

    # =========================================================
    # FACEBOOK
    # =========================================================

    if result_state.Metadata.facebook:

        print_facebook_result(
            result_state.facebook_result
        )

    # =========================================================
    # YOUTUBE
    # =========================================================

    if result_state.Metadata.youtube:

        print_youtube_result(
            result_state.youtube_result
        )

    # =========================================================
    # TIKTOK
    # =========================================================

    if result_state.Metadata.tiktok:

        print_tiktok_result(
            result_state.tiktok_result
        )

    # =========================================================
    # SUMMARY
    # =========================================================

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(
        result_state.summary_result.summary_result
    )

    return result_state


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    run(request)