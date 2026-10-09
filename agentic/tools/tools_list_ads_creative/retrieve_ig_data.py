from langchain_core.tools import tool
from agentic.config.dashboard_integration import AdsDashboardApiClient
from agentic.services.ads_services.creative_service import CreativeAdsService

api_client = AdsDashboardApiClient()
service = CreativeAdsService(api_client)

@tool
def retrieval_reach_data(client_code: str, period_id: str, campaign_ids: list[str] | None = None) -> dict:
    """
    Retrieve reach data based on client code and period 
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="instagram",
        objective="reach",
        campaign_ids=campaign_ids,
    )

@tool
def retrieval_profilevisit_data(client_code: str, period_id: str, campaign_ids: list[str] | None = None) -> dict:
    """
    Retrieve profile visit data based on client code and period 
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="instagram",
        objective="profilevisit",
        campaign_ids=campaign_ids,
    )

@tool
def retrieval_engagement_data(client_code: str, period_id: str, campaign_ids: list[str] | None = None) -> dict:
    """
    Retrieve engagement data based on client code and period 
    """

    return service.retrieve(
        client_code=client_code,
        period_id=period_id,
        platform="instagram",
        objective="engagement",
        campaign_ids=campaign_ids,
    )


    
    