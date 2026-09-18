from langchain_core.tools import tool

from agentic.config.dashboard_integration import AdsDashboardApiClient
from agentic.services.ads_services.adset_service import AdSetAdsService


api_client = AdsDashboardApiClient()

service = AdSetAdsService(api_client)


@tool
def reach_retrieval(
    client_code: str,
    period_id: str,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict:
    """
    Retrieve Meta adset reach data.
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="meta",
        objective="reach",
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )


@tool
def engagement_retrieval(
    client_code: str,
    period_id: str,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict:
    """
    Retrieve Meta adset engagement data.
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="meta",
        objective="engagement",
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )


@tool
def leads_retrieval(
    client_code: str,
    period_id: str,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict:
    """
    Retrieve Meta adset leads data.
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="meta",
        objective="leads",
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )


@tool
def linkclicks_retrieval(
    client_code: str,
    period_id: str,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict:
    """
    Retrieve Meta adset link clicks data.
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="meta",
        objective="linkclicks",
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )


@tool
def views_retrieval(
    client_code: str,
    period_id: str,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict:
    """
    Retrieve Meta adset views data.
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="meta",
        objective="views",
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )