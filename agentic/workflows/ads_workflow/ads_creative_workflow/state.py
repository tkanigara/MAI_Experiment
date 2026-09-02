from datetime import date
from typing import Any
from pydantic import BaseModel, Field

class Request(BaseModel):
    client_code: str
    period_id: str

    analysis_type: str
    platform_scope: str
    objective: str

    campaign_ids: list[str] = Field(default_factory=list)
    adset_ids: list[str] = Field(default_factory=list)
    # Breakdowns are intentionally opt-in because a creative detail call can
    # fan out into many placement/demographic/region requests.
    include_breakdowns: bool = False

    generate_slides: bool = False
    slides_dry_run: bool = False
    persist_insights: bool = True
    reuse_cached_insights: bool = True
    
class MetaData(BaseModel):
    client_id: str | None = None
    client_code:str | None = None
    client_name:str | None = None
    report_period_id: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    instagram: bool =  False
    facebook: bool = False
    tiktok: bool = False
    youtube: bool = False
    linkedin: bool = False
    threads: bool = False
    ads_platforms: list[str] = Field(default_factory=list)
    meta_ad_accounts: list[dict[str, Any]] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    loaded: bool = False
    error: str | None = None


class AdsRetrievalData(BaseModel):
    """Canonical retrieval payload shared by Ads analysis agents.

    This is transient workflow state, not a second database.  The dashboard
    API remains responsible for active snapshot selection, objective mapping,
    metric configuration, and editor overrides.
    """

    status: str = "not_loaded"
    success: bool = False
    error: str | None = None
    client: dict[str, Any] = Field(default_factory=dict)
    period: dict[str, Any] = Field(default_factory=dict)
    analysis_type: str | None = None
    platform_scope: str | None = None
    objective: str | None = None
    objectives: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    display_metrics: list[dict[str, Any]] = Field(default_factory=list)
    available_filters: dict[str, Any] = Field(default_factory=dict)
    breakdowns: dict[str, Any] = Field(default_factory=dict)
    # Stable projections used by the objective agents.  ``breakdowns`` keeps
    # the dashboard's entity-keyed response for compatibility; ``sections``
    # gives each analysis area its own bounded input.
    sections: dict[str, Any] = Field(default_factory=dict)
    unconfirmed_count: int = 0
    warnings: list[str] = Field(default_factory=list)

class TaskDelegation(BaseModel):
    client_code: str | None = None
    runner: str | None = None

class InstagramMetricAnalysis(BaseModel):
    client_code: str | None = None
    objective: str | None = None

    # Generic fields are used for canonical objectives such as Leads, Views,
    # and Link Clicks.  The legacy objective-specific fields below remain for
    # compatibility with existing report prompts.
    performance_overview: str | None = None
    content_analysis: str | None = None
    placement_analysis: str | None = None
    audience_demographic_analysis: str | None = None
    region_analysis: str | None = None
    optimisation_action: str | None = None

    performance_overview_reach: str | None = None
    performance_overview_engagement: str | None = None
    performance_overview_profilevisit: str | None = None

    content_analysis_reach: str | None = None
    content_analysis_engagement: str | None = None
    content_analysis_profilevisit: str | None = None

    placement_analysis_reach: str | None = None
    placement_analysis_engagement: str | None = None
    placement_analysis_profilevisit: str | None = None

    audience_demographic_analysis_reach: str | None = None
    audience_demographic_analysis_engagement: str | None = None
    audience_demographic_analysis_profilevisit: str | None = None

    region_analysis_reach: str | None = None
    region_analysis_engagement: str | None = None
    region_analysis_profilevisit: str | None = None

    optimisation_action_reach: str | None = None
    optimisation_action_engagement: str | None = None
    optimisation_action_profilevisit: str | None = None

class FacebookMetricAnalysis(BaseModel):
    client_code: str | None = None
    objective: str | None = None

    performance_overview: str | None = None
    content_analysis: str | None = None
    placement_analysis: str | None = None
    audience_demographic_analysis: str | None = None
    region_analysis: str | None = None
    optimisation_action: str | None = None

    performance_overview_reach: str | None = None
    performance_overview_engagement: str | None = None
    performance_overview_profilevisit: str | None = None
    performance_overview_pagelike: str | None = None

    content_analysis_reach: str | None = None
    content_analysis_engagement: str | None = None
    content_analysis_profilevisit: str | None = None
    content_analysis_pagelike: str | None = None

    placement_analysis_reach: str | None = None
    placement_analysis_engagement: str | None = None
    placement_analysis_profilevisit: str | None = None
    placement_analysis_pagelike: str | None = None

    audience_demographic_analysis_reach: str | None = None
    audience_demographic_analysis_engagement: str | None = None
    audience_demographic_analysis_profilevisit: str | None = None
    audience_demographic_analysis_pagelike: str | None = None

    region_analysis_reach: str | None = None
    region_analysis_engagement: str | None = None
    region_analysis_profilevisit: str | None = None
    region_analysis_pagelike: str | None = None

    optimisation_action_reach: str | None = None
    optimisation_action_engagement: str | None = None
    optimisation_action_profilevisit: str | None = None
    optimisation_action_pagelike: str | None = None

class YoutubeMetricAnalysis(BaseModel):
    client_code: str | None = None

    performance_overview_impressions: str | None = None
    performance_overview_views: str | None = None

    audience_demographics_impressions: str | None = None
    audience_demographics_views: str | None = None

    region_breakdown_impressions: str | None = None
    region_breakdown_views: str | None = None

    testing_optimization_impressions: str | None = None
    testing_optimization_views: str | None = None

    bidding_optimisation_impressions: str | None = None
    bidding_optimisation_views: str | None = None


class TiktokMetricAnalysis(BaseModel):
    client_code: str | None = None

    performance_overview_views: str |  None = None
    performance_overview_follow: str | None = None

    audience_demographic_views: str | None = None
    audience_demographic_follow: str | None = None

    region_breakdown_views: str | None = None
    region_breakdown_follow: str | None = None

    optimisation_views: str | None = None
    optimisation_follow: str | None = None


class SummaryAll(BaseModel):
    client_code: str | None = None
    summary_result: str | None = None

class State(BaseModel):
    #request
    request: Request

    #metadata
    Metadata: MetaData = Field(default_factory=MetaData)

    # One canonical dashboard response.  Analysis agents read this field;
    # they should not issue their own SQL/API queries.
    ads_data: AdsRetrievalData = Field(default_factory=AdsRetrievalData)

    #delegation
    Task_delegation: list[TaskDelegation]= Field(default_factory=list)

    #runner routing
    routes: list[str] = Field(default_factory=list)

    #Analysis result
    instagram_result: InstagramMetricAnalysis = Field(default_factory=InstagramMetricAnalysis)
    facebook_result: FacebookMetricAnalysis = Field(default_factory=FacebookMetricAnalysis)
    youtube_result: YoutubeMetricAnalysis = Field(default_factory=YoutubeMetricAnalysis)
    tiktok_result: TiktokMetricAnalysis = Field(default_factory=TiktokMetricAnalysis)

    #Class Summary
    summary_result: SummaryAll = Field(default_factory=SummaryAll)
