from datetime import date
from pydantic import BaseModel, Field

class Request(BaseModel):
    client_code: str
    period_id: str

    analysis_type: str
    platform_scope: str
    objective: str

    campaign_ids: list[str] = Field(default_factory=list)
    adset_ids: list[str] = Field(default_factory=list)

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
    loaded: bool = False
    error: str | None = None

class TaskDelegation(BaseModel):
    client_code: str | None = None
    runner: str | None = None

class InstagramMetricAnalysis(BaseModel):
    client_code: str | None = None

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