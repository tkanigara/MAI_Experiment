"""Structured Ads retrieval backed by the dashboard API."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agentic.clients.ads_dashboard_client import (
    AdsDashboardClient,
    AdsDashboardClientError,
)


def _normalise_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def retrieve_ads_data(
    client_code: str,
    period_id: str,
    analysis_type: str = "creative",
    platform_scope: str = "meta",
    objective: str = "",
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    include_breakdowns: bool = False,
    max_breakdowns: int = 20,
    client: AdsDashboardClient | None = None,
) -> dict[str, Any]:
    """Return one canonical, analysis-ready Ads payload.

    The returned shape intentionally mirrors the dashboard response while
    adding resolved client/period context.  Numeric nulls are preserved; the
    retrieval layer never converts unavailable metrics to zero.
    """

    api = client or AdsDashboardClient()
    try:
        resolved_client, resolved_period = api.resolve_client_and_period(
            client_code, period_id
        )
        scope = str(platform_scope or "meta").strip().lower()
        if scope not in {"meta", "instagram", "facebook"}:
            # YouTube and TikTok are catalogued in the dashboard but their
            # ingestion endpoints are intentionally not active yet.
            return {
                "status": "coming_soon",
                "success": False,
                "client": {
                    "id": resolved_client.get("id"),
                    "code": resolved_client.get("client_code"),
                    "name": resolved_client.get("client_name"),
                    "ads_platforms": (resolved_client.get("ads_configuration") or {}).get("platforms", [])
                    if isinstance(resolved_client.get("ads_configuration"), dict)
                    else [],
                    "meta_ad_accounts": resolved_client.get("meta_ad_accounts", []),
                },
                "period": {
                    "id": resolved_period.get("id"),
                    "label": resolved_period.get("period_label") or resolved_period.get("label"),
                    "start": resolved_period.get("period_start"),
                    "end": resolved_period.get("period_end"),
                },
                "analysis_type": analysis_type,
                "platform_scope": scope,
                "objective": objective or None,
                "summary": {},
                "rows": [],
                "warnings": [f"{scope.title()} Ads ingestion is coming soon."],
            }
        response = api.get_analysis(
            client_id=str(resolved_client["id"]),
            period_id=str(resolved_period["id"]),
            analysis_type=analysis_type,
            platform_scope=platform_scope,
            objective=objective,
            campaign_ids=_normalise_list(campaign_ids),
            adset_ids=_normalise_list(adset_ids),
        )
    except AdsDashboardClientError as exc:
        return {
            "status": "error",
            "success": False,
            "error": str(exc),
            "warnings": [],
            "rows": [],
            "summary": {},
        }

    requested_objective = str(objective or "").strip().lower().replace(" ", "_")
    actual_objective = str(response.get("objective") or "").strip().lower().replace(" ", "_")
    if requested_objective and actual_objective and requested_objective != actual_objective:
        # The dashboard keeps legacy compatibility by falling back to the
        # first confirmed objective when a requested mapping is unavailable.
        # Retrieval must not silently label that data as the requested goal.
        return {
            "status": "objective_mismatch",
            "success": False,
            "client": {
                "id": resolved_client.get("id"),
                "code": resolved_client.get("client_code"),
                "name": resolved_client.get("client_name"),
                "ads_platforms": (
                    (resolved_client.get("ads_configuration") or {}).get("platforms", [])
                    if isinstance(resolved_client.get("ads_configuration"), dict)
                    else []
                ),
                "meta_ad_accounts": resolved_client.get("meta_ad_accounts", []),
            },
            "period": {
                "id": resolved_period.get("id"),
                "label": resolved_period.get("period_label") or resolved_period.get("label"),
                "start": resolved_period.get("period_start"),
                "end": resolved_period.get("period_end"),
            },
            "analysis_type": response.get("dimension", analysis_type),
            "platform_scope": response.get("platform_scope", platform_scope),
            "objective": actual_objective or None,
            "objectives": response.get("objectives", []),
            "source": response.get("source") or {},
            "summary": {},
            "rows": [],
            "warnings": [
                f"Requested objective '{objective}' is not mapped for this period; dashboard returned '{response.get('objective')}'. Confirm the campaign mapping before analysis."
            ],
        }

    warnings = list(response.get("warnings") or [])
    breakdowns: dict[str, Any] = {}
    if include_breakdowns and response.get("data_status") == "ready":
        # Keep this bounded: one creative/ad-set can have several breakdown
        # rows and the result is intended to be passed to an LLM.
        limit = max(1, min(int(max_breakdowns or 20), 50))
        rows = (response.get("rows") or [])[:limit]
        for row in rows:
            entity_id = row.get("id")
            if not entity_id:
                continue
            try:
                if str(analysis_type).lower() == "adset":
                    detail = api.get_adset_creatives(
                        client_id=str(resolved_client["id"]),
                        period_id=str(resolved_period["id"]),
                        adset_id=str(entity_id),
                        platform_scope=platform_scope,
                        objective=objective,
                    )
                else:
                    detail = api.get_creative_detail(
                        client_id=str(resolved_client["id"]),
                        period_id=str(resolved_period["id"]),
                        creative_id=str(entity_id),
                        platform_scope=platform_scope,
                    )
                breakdowns[str(entity_id)] = detail
            except AdsDashboardClientError as exc:
                warnings.append(f"Breakdown unavailable for {entity_id}: {exc}")

    return {
        "status": response.get("data_status", "ready"),
        "success": response.get("data_status") == "ready",
        "client": {
            "id": resolved_client.get("id"),
            "code": resolved_client.get("client_code"),
            "name": resolved_client.get("client_name"),
            "ads_platforms": (
                (resolved_client.get("ads_configuration") or {}).get("platforms", [])
                if isinstance(resolved_client.get("ads_configuration"), dict)
                else []
            ),
            "meta_ad_accounts": resolved_client.get("meta_ad_accounts", []),
        },
        "period": {
            "id": resolved_period.get("id"),
            "label": resolved_period.get("period_label") or resolved_period.get("label"),
            "start": resolved_period.get("period_start"),
            "end": resolved_period.get("period_end"),
        },
        "analysis_type": response.get("dimension", analysis_type),
        "platform_scope": response.get("platform_scope", platform_scope),
        "objective": response.get("objective") or objective or None,
        "objectives": response.get("objectives", []),
        "source": response.get("source") or {
            "type": resolved_period.get("active_source"),
            "import_id": resolved_period.get("import_id"),
            "updated_at": resolved_period.get("sync_completed_at")
            or resolved_period.get("imported_at"),
        },
        "summary": response.get("summary") or {},
        "rows": response.get("rows") or [],
        "display_metrics": response.get("display_metrics") or [],
        "available_filters": response.get("available_filters") or {},
        "unconfirmed_count": response.get("unconfirmed_count", 0),
        "breakdowns": breakdowns,
        "warnings": warnings,
    }


@tool
def retrieve_ads_data_tool(
    client_code: str,
    period_id: str,
    analysis_type: str = "creative",
    platform_scope: str = "meta",
    objective: str = "",
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    include_breakdowns: bool = False,
) -> dict[str, Any]:
    """LangChain tool wrapper around :func:`retrieve_ads_data`."""

    return retrieve_ads_data(
        client_code=client_code,
        period_id=period_id,
        analysis_type=analysis_type,
        platform_scope=platform_scope,
        objective=objective,
        campaign_ids=campaign_ids,
        adset_ids=adset_ids,
        include_breakdowns=include_breakdowns,
    )
