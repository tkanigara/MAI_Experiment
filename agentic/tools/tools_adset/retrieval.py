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


def retrieve_adset_report_data(
    client_code: str,
    period_id: str,
    platform_scope: str = "meta",
    objectives: list[str] | None = None,
    objective: str = "",
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return the complete dashboard-backed input for Ad Set analysis."""

    return retrieve_ads_data(
        client_code=client_code,
        period_id=period_id,
        analysis_type="adset",
        platform_scope=platform_scope,
        objectives=objectives,
        objective=objective,
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
        include_breakdowns=True,
    )


def objective_overview(payload: dict[str, Any], objective: str) -> dict[str, Any]:
    """Select the objective-level KPI and Ad Set comparison section."""

    return dict(
        ((payload.get("objective_data") or {}).get(str(objective).lower()) or {}).get(
            "objective_overview"
        )
        or {}
    )


def adset_breakdowns(payload: dict[str, Any], objective: str) -> dict[str, Any]:
    """Select creatives grouped under each Ad Set for one objective."""

    return dict(
        ((payload.get("objective_data") or {}).get(str(objective).lower()) or {}).get(
            "adset_breakdowns"
        )
        or {}
    )


@tool
def retrieval(
    client_code: str,
    period_id: str,
    platform_scope: str = "meta",
    objectives: list[str] | None = None,
    objective: str = "",
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Retrieve comparison and creative breakdown data for each Ad Set objective."""

    return retrieve_adset_report_data(
        client_code=client_code,
        period_id=period_id,
        platform_scope=platform_scope,
        objectives=objectives,
        objective=objective,
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
    )

