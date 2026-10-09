from typing import Any

from pydantic import BaseModel, Field


class Request(BaseModel):
    client_code: str | None = None
    period_id: str | None = None
    analysis_type: str
    platform_scope: list[str] =  Field(default_factory=list)

    objectives: list[str] = Field(
        default_factory=list
    )

    campaign_ids: list[str] = Field(
        default_factory=list
    )

    adset_ids: list[str] = Field(
        default_factory=list
    )


class TaskDelegation(BaseModel):
    runner: str
    platform: str
    objectives: list[str] = Field(
        default_factory=list
    )


class MetaAnalysis(BaseModel):

    overall_reach_analysis: str | None = None
    overall_engagement_analysis: str | None = None
    overall_leads_analysis: str | None = None
    overall_views_analysis: str | None = None
    overall_linkclicks_analysis: str | None = None
    
    reach_adset_analysis: str | None = None
    engagement_adset_analysis: str | None = None
    leads_adset_analysis: str | None = None
    views_adset_analysis: str | None = None
    linkclicks_adset_analysis: str | None = None


class MetaSummary(BaseModel):
    summary_result: str | None = None


class State(BaseModel):

    request: Request

    # Optional frozen dashboard evidence supplied by the slide generator.
    # Interactive workflow runs leave this empty and retrieve from the API.
    adset_data: dict[str, dict[str, Any]] = Field(default_factory=dict)

    task_delegation: list[TaskDelegation] = Field(
        default_factory=list
    )

    meta_analysis: MetaAnalysis = Field(
        default_factory=MetaAnalysis
    )

    meta_summary: MetaSummary = Field(
        default_factory=MetaSummary
    )
