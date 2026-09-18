from typing import Any
from langchain_core.tools import tool
from agentic.config.dashboard_integration import AdsDashboardApiClient
from agentic.services.ads_services.creative_service import CreativeAdsService


api_client = AdsDashboardApiClient()
creative_service = CreativeAdsService(api_client=api_client)


@tool
def retrieve_creative_metadata(client_code: str, period_id: str,) -> dict[str, Any]:
    """
    Retrieve metadata required by the Creative Ads workflow.

    The metadata is used to populate State.Metadata
    and determine which platform runners are available.
    """

    return creative_service.retrieve_metadata(
        client_code=client_code,
        period_id=period_id,
    )