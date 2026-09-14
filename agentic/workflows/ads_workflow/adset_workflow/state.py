from datetime import date
from pydantic import BaseModel, Field

class Request(BaseModel):
    client_code: str | None = None
    period_id: str | None = None
    analysis_type: str
    platform_scope: str
    objectives: list[str] = Field(default_factory=list)

class AdsetData(BaseModel):
    client_code: str | None = None
    period_id: str | None = None
    overall_views_data_meta: 
    overall_reach_data_meta:
    overall_engagement_meta:
    overall_linkclicks_meta:
    overall_leads_meta:

    campaign_views_data_meta:
    campaign_reach_data_meta:
    campaign_engagement_meta:
    campaign_linkclicks_meta:
    campaign_leads_meta: 

class MetaAnalysis(BaseModel):
    overall_reach_analysis: str | None = None
    overall_engagement_analysis: str | None = None
    overall_leads_analysis: str | None = None
    overalll_views_analysis: str | None = None
    overall_linkclicks_analysis: str | None = None

    reach_campaign_analysis: str | None = None
    engagement_campaign_analysis: str | None = None
    leads_campaign_analysis: str | None = None
    views_campaign_analysis: str | None = None
    linkclicks_analysis: str | None


class GoogleAdsAnalysis(BaseModel):
    pass
class State(BaseModel):
    request: Request

