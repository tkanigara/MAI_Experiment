from typing_extensions import List
from datetime import date
from pydantic import BaseModel, Field


class Request(BaseModel):
    user_intent: str
    client_code: str | None = None
    report_date: date | None = None

class MetaData(BaseModel):
    client_code:str | None = None
    client_name:str | None = None
    instagram: bool =  False
    facebook: bool = False
    tiktok: bool = False
    youtube: bool = False
    loaded: bool = False

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
    
class Summary(BaseModel):
    client_code: str | None = None
    summary_result : str | None = None

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

    #Summary  result
    summary_result : Summary = Field(default_factory=Summary)
    summary_instagram: SummaryInstagram = Field(default_factory=SummaryInstagram)
    summary_facebook: SummaryFacebook = Field(default_factory=SummaryFacebook)
    summary_tiktok: SummaryTiktok = Field(default_factory=SummaryTiktok)
    sumamry_youtube: SummaryYoutube = Field(default_factory=SummaryYoutube)





    














    
    
