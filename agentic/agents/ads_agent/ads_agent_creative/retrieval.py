"""Initial Ads workflow retrieval node.

Ads analysis loads the dashboard response once and hands it to downstream
nodes through ``State.ads_data``.  Objective agents therefore do not need to
know SQL or dashboard endpoint details.
"""

from __future__ import annotations

from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_data,
)
from agentic.utils.logger import node
from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    AdsRetrievalData,
    MetaData,
    State,
)


def _metadata_from_payload(payload: AdsRetrievalData, state: State) -> MetaData:
    client = payload.client or {}
    period = payload.period or {}
    scope = str(payload.platform_scope or state.request.platform_scope or "").lower()
    configured_platforms = client.get("ads_platforms") or []
    if not configured_platforms:
        configured_platforms = [scope] if scope else []
    configured_platforms = [str(item).lower() for item in configured_platforms]

    return MetaData(
        client_id=str(client.get("id")) if client.get("id") else None,
        client_code=client.get("code") or state.request.client_code,
        client_name=client.get("name"),
        report_period_id=str(period.get("id")) if period.get("id") else None,
        period_start=period.get("start"),
        period_end=period.get("end"),
        instagram="instagram" in configured_platforms or scope in {"meta", "instagram"},
        facebook="facebook" in configured_platforms or scope in {"meta", "facebook"},
        tiktok="tiktok" in configured_platforms,
        youtube="youtube" in configured_platforms,
        ads_platforms=configured_platforms,
        meta_ad_accounts=client.get("meta_ad_accounts") or [],
        source=payload.source,
        warnings=payload.warnings,
        loaded=True,
    )


def retrieval_agent(state: State) -> dict:
    """Resolve the client/period and load one canonical Ads payload."""

    with node("Retrieve Ads Data"):
        if state.ads_data.status not in {"not_loaded", "error"}:
            return {"Metadata": state.Metadata, "ads_data": state.ads_data}

        payload = AdsRetrievalData(
            **retrieve_ads_data(
                client_code=state.request.client_code,
                period_id=state.request.period_id,
                analysis_type=state.request.analysis_type,
                platform_scope=state.request.platform_scope,
                objectives=state.request.objectives,
                campaign_ids=state.request.campaign_ids,
                adset_ids=state.request.adset_ids,
                include_breakdowns=state.request.include_breakdowns,
            )
        )
        metadata = _metadata_from_payload(payload, state)
        if payload.status == "error":
            metadata = metadata.model_copy(
                update={"loaded": False, "error": payload.error}
            )
        return {"Metadata": metadata, "ads_data": payload}
