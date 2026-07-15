from datetime import date
from pydantic import BaseModel, Field


class Request(BaseModel):
    user_intent: str
    client_code: str | None = None
    report_date: date | None = None
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
    loaded: bool = False
    error: str | None = None

class instagram_result_analysis(BaseModel):
    client_code: str | None = None
    client_name: str | None = None
    kpi_analysis: str | None = None
    socmed_overview_analysis: str | None = None
    followers_growth_analysis: str | None = None
    growth_performance_analysis: str | None = None
    top_content_performance: str | None = None

class facebook_result_analysis(BaseModel):
    client_code: str | None = None
    client_name: str | None = None
    kpi_analysis: str | None = None
    socmed_overview_analysis: str | None = None
    followers_growth_analysis: str | None = None
    growth_performance_analysis: str | None = None
    top_content_performance: str | None = None

class tiktok_result_analysis(BaseModel):
    client_code: str | None = None
    client_name: str | None = None
    kpi_analysis: str | None = None
    socmed_overview_analysis: str | None = None
    followers_growth_analysis: str | None = None
    growth_performance_analysis: str | None = None
    top_content_performance: str | None = None

class youtube_result_analysis(BaseModel):
    client_code: str | None = None
    client_name: str | None = None
    kpi_analysis: str | None = None
    socmed_overview_analysis: str | None = None
    followers_growth_analysis: str | None = None
    growth_performance_analysis: str | None = None
    top_content_performance: str | None = None

class SummaryInstagram(BaseModel):
    client_code: str | None = None
    key_summary: str | None = None
    action_plan: str | None = None

class SummaryFacebook(BaseModel):
    client_code: str | None = None
    key_summary: str | None = None
    action_plan: str | None = None

class SummaryTiktok(BaseModel):
    client_code: str | None = None
    key_summary: str | None = None
    action_plan: str | None = None

class SummaryYoutube(BaseModel):
    client_code: str | None = None
    key_summary: str | None = None
    action_plan: str | None = None
    
class ReportGenerationResult(BaseModel):
    status: str = "not_requested"
    presentation_id: str | None = None
    presentation_url: str | None = None
    report_name: str | None = None
    error: str | None = None

class State(BaseModel):
    #request
    request: Request

    #metadata
    Metadata: MetaData = Field(default_factory=MetaData)

    #Routing
    routes: list[str] = Field(default_factory=list)

    #Analysis Result
    instagram_result: instagram_result_analysis = Field(default_factory=instagram_result_analysis)
    facebook_result: facebook_result_analysis = Field(default_factory=facebook_result_analysis)
    tiktok_result: tiktok_result_analysis = Field(default_factory=tiktok_result_analysis)
    youtube_result: youtube_result_analysis = Field(default_factory=youtube_result_analysis)

    # Per-platform summary results
    summary_instagram: SummaryInstagram = Field(default_factory=SummaryInstagram)
    summary_facebook: SummaryFacebook = Field(default_factory=SummaryFacebook)
    summary_tiktok: SummaryTiktok = Field(default_factory=SummaryTiktok)
    summary_youtube: SummaryYoutube = Field(default_factory=SummaryYoutube)

    # Google Slides generation result
    report_generation: ReportGenerationResult = Field(default_factory=ReportGenerationResult)

    # Analysis cache status
    analysis_cache_hit: bool = False
    analysis_data_version: str | None = None





    














    
    
