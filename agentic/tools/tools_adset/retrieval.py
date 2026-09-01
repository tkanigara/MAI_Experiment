"""Compatibility wrapper for Ad Set retrieval.

Ad Set and Creative analysis share the same canonical dashboard payload.  The
wrapper keeps the old import path working while routing calls through the
single Ads retrieval implementation.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agentic.tools.tools_list_ads_creative.dashboard_retrieval import (
    retrieve_ads_data,
)


@tool
def retrieval(
    client_code: str,
    period_id: str,
    platform_scope: str = "meta",
    objective: str = "",
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Retrieve dashboard-backed Ad Set performance data."""

    return retrieve_ads_data(
        client_code=client_code,
        period_id=period_id,
        analysis_type="adset",
        platform_scope=platform_scope,
        objective=objective,
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )

