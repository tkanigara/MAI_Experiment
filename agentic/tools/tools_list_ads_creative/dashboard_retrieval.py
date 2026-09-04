"""Structured Ads retrieval backed by the dashboard API."""

from __future__ import annotations

from collections.abc import Mapping
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


def _breakdown_rows(
    payload: Mapping[str, Any] | None,
    key: str,
) -> list[dict[str, Any]]:
    """Flatten per-entity dashboard details into analysis-ready rows.

    The dashboard creative-detail endpoint returns breakdowns keyed by
    creative/ad-set id.  Keeping the entity id and name on every row makes
    the result useful to an agent without asking it to reconstruct that
    relationship from nested JSON.
    """

    rows: list[dict[str, Any]] = []
    for entity_id, detail in ((payload or {}).get("breakdowns") or {}).items():
        if not isinstance(detail, Mapping):
            continue
        creative = detail.get("creative") or {}
        if not isinstance(creative, Mapping):
            creative = {}
        entity_name = (
            creative.get("ad_name")
            or creative.get("name")
            or str(entity_id)
        )
        for item in detail.get(key) or []:
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    "entity_id": str(entity_id),
                    "entity_name": entity_name,
                    **dict(item),
                }
            )
    return rows


def retrieve_performance_overview(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the report-level performance metrics from a dashboard payload."""

    return dict((payload or {}).get("summary") or {})


def retrieve_content_analysis(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return creative/ad-set rows used for content analysis."""

    return [dict(row) for row in ((payload or {}).get("rows") or []) if isinstance(row, Mapping)]


def retrieve_placement_analysis(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return placement rows, annotated with their creative/ad-set owner."""

    return _breakdown_rows(payload, "placements")


def retrieve_audience_demographic_analysis(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return age/gender rows, annotated with their creative/ad-set owner."""

    return _breakdown_rows(payload, "demographics")


def retrieve_region_analysis(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return region rows, annotated with their creative/ad-set owner."""

    return _breakdown_rows(payload, "regions")


def retrieve_ads_sections(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Split one canonical dashboard response into the LLM analysis sections.

    This is deliberately a pure local projection: it does not make additional
    dashboard requests.  Call :func:`retrieve_ads_data` once, with
    ``include_breakdowns=True`` when placement, audience, or region analysis
    is required, then pass its result here.
    """

    return {
        "performance_overview": retrieve_performance_overview(payload),
        "content_analysis": retrieve_content_analysis(payload),
        "placement_analysis": retrieve_placement_analysis(payload),
        "audience_demographic_analysis": retrieve_audience_demographic_analysis(payload),
        "region_analysis": retrieve_region_analysis(payload),
    }


def retrieve_ads_data(
    client_code: str,
    period_id: str,
    analysis_type: str = "creative",
    platform_scope: str = "meta",
    objectives: list[str] | None = None,
    objective: str | None = None,
    campaign_ids: list[str] | None = None,
    adset_ids: list[str] | None = None,
    include_breakdowns: bool = False,
    max_breakdowns: int = 20,
    client: AdsDashboardClient | None = None,
) -> dict[str, Any]:
    """Return one canonical, multi-objective Ads payload.

    The dashboard API remains the source of truth. Each requested objective
    is retrieved independently and stored under ``objective_data`` so
    downstream objective agents can consume only the data they need.
    """

    api = client or AdsDashboardClient()

    requested_values = list(objectives or [])
    if not requested_values and objective:
        requested_values = [objective]

    requested_objectives = [
        str(item).strip().lower().replace(" ", "_")
        for item in requested_values
        if str(item).strip()
    ]
    requested_objectives = list(dict.fromkeys(requested_objectives))

    try:
        resolved_client, resolved_period = api.resolve_client_and_period(
            client_code,
            period_id,
        )

        scope = str(
            platform_scope or "meta"
        ).strip().lower()

        if scope not in {"meta", "instagram", "facebook"}:
            return {
                "status": "coming_soon",
                "success": False,
                "client": {
                    "id": resolved_client.get("id"),
                    "code": resolved_client.get("client_code"),
                    "name": resolved_client.get("client_name"),
                    "ads_platforms": (
                        (resolved_client.get("ads_configuration") or {}).get(
                            "platforms",
                            [],
                        )
                        if isinstance(
                            resolved_client.get("ads_configuration"),
                            dict,
                        )
                        else []
                    ),
                    "meta_ad_accounts": resolved_client.get(
                        "meta_ad_accounts",
                        [],
                    ),
                },
                "period": {
                    "id": resolved_period.get("id"),
                    "label": (
                        resolved_period.get("period_label")
                        or resolved_period.get("label")
                    ),
                    "start": resolved_period.get("period_start"),
                    "end": resolved_period.get("period_end"),
                },
                "analysis_type": analysis_type,
                "platform_scope": scope,
                "objectives": requested_objectives,
                "objective_data": {},
                "summary": {},
                "rows": [],
                "warnings": [
                    f"{scope.title()} Ads ingestion is coming soon."
                ],
            }

    except AdsDashboardClientError as exc:
        return {
            "status": "error",
            "success": False,
            "error": str(exc),
            "warnings": [],
            "objectives": requested_objectives,
            "objective_data": {},
            "rows": [],
            "summary": {},
        }

    # ------------------------------------------------------------------
    # Retrieve each requested objective independently.
    # ------------------------------------------------------------------

    objective_data: dict[str, Any] = {}
    warnings: list[str] = []

    campaign_list = _normalise_list(campaign_ids)
    adset_list = _normalise_list(adset_ids)

    for objective in requested_objectives:

        try:
            response = api.get_analysis(
                client_id=str(resolved_client["id"]),
                period_id=str(resolved_period["id"]),
                analysis_type=analysis_type,
                platform_scope=platform_scope,
                objective=objective,
                campaign_ids=campaign_list,
                adset_ids=adset_list,
            )
            print("\n========== OBJECTIVE DEBUG ==========")
            print("Requested objective :", objective)
            print("Returned objective  :", response.get("objective"))
            print("Data status         :", response.get("data_status"))
            print("Response keys       :", list(response.keys()))
            print("=====================================")

        except AdsDashboardClientError as exc:
            warnings.append(
                f"Objective '{objective}' retrieval failed: {exc}"
            )

            objective_data[objective] = {
                "status": "error",
                "success": False,
                "objective": objective,
                "summary": {},
                "rows": [],
                "display_metrics": [],
                "available_filters": {},
                "breakdowns": {},
                "sections": {},
                "warnings": [str(exc)],
            }

            continue

        requested_objective = (
            str(objective or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )

        actual_objective = (
            str(response.get("objective") or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )

        # --------------------------------------------------------------
        # Objective mismatch
        # --------------------------------------------------------------

        if (
            requested_objective
            and actual_objective
            and requested_objective != actual_objective
        ):
            warning = (
                f"Requested objective '{objective}' is not mapped "
                f"for this period; dashboard returned "
                f"'{response.get('objective')}'. "
                f"Confirm the campaign mapping before analysis."
            )

            warnings.append(warning)

            objective_data[objective] = {
                "status": "objective_mismatch",
                "success": False,
                "objective": actual_objective or None,
                "requested_objective": requested_objective,
                "summary": {},
                "rows": [],
                "display_metrics": [],
                "available_filters": {},
                "breakdowns": {},
                "sections": {},
                "warnings": [warning],
            }

            continue

        # --------------------------------------------------------------
        # Normal successful response
        # --------------------------------------------------------------

        objective_warnings = list(
            response.get("warnings") or []
        )

        breakdowns: dict[str, Any] = {}

        if (
            include_breakdowns
            and response.get("data_status") == "ready"
        ):

            # Keep this bounded because breakdown data is eventually
            # passed to an LLM.
            limit = max(
                1,
                min(
                    int(max_breakdowns or 20),
                    50,
                ),
            )

            rows = (
                response.get("rows") or []
            )[:limit]

            for row in rows:

                entity_id = row.get("id")

                if not entity_id:
                    continue

                try:

                    if str(analysis_type).lower() == "adset":

                        detail = api.get_adset_creatives(
                            client_id=str(
                                resolved_client["id"]
                            ),
                            period_id=str(
                                resolved_period["id"]
                            ),
                            adset_id=str(entity_id),
                            platform_scope=platform_scope,
                            objective=objective,
                        )

                    else:

                        detail = api.get_creative_detail(
                            client_id=str(
                                resolved_client["id"]
                            ),
                            period_id=str(
                                resolved_period["id"]
                            ),
                            creative_id=str(entity_id),
                            platform_scope=platform_scope,
                        )

                    breakdowns[str(entity_id)] = detail

                except AdsDashboardClientError as exc:

                    objective_warnings.append(
                        f"Breakdown unavailable for "
                        f"{entity_id}: {exc}"
                    )

        # --------------------------------------------------------------
        # Build objective-specific payload
        # --------------------------------------------------------------

        objective_payload = {
            "status": response.get(
                "data_status",
                "ready",
            ),

            "success": (
                response.get("data_status") == "ready"
            ),

            "objective": (
                response.get("objective")
                or objective
                or None
            ),

            "analysis_type": response.get(
                "dimension",
                analysis_type,
            ),

            "platform_scope": response.get(
                "platform_scope",
                platform_scope,
            ),

            "source": response.get(
                "source"
            ) or {
                "type": resolved_period.get(
                    "active_source"
                ),
                "import_id": resolved_period.get(
                    "import_id"
                ),
                "updated_at": (
                    resolved_period.get(
                        "sync_completed_at"
                    )
                    or resolved_period.get(
                        "imported_at"
                    )
                ),
            },

            "summary": (
                response.get("summary")
                or {}
            ),

            "rows": (
                response.get("rows")
                or []
            ),

            "display_metrics": (
                response.get("display_metrics")
                or []
            ),

            "available_filters": (
                response.get("available_filters")
                or {}
            ),

            "unconfirmed_count": response.get(
                "unconfirmed_count",
                0,
            ),

            "breakdowns": breakdowns,

            "warnings": objective_warnings,
        }

        # Build the existing analysis sections.
        objective_payload["sections"] = retrieve_ads_sections(
            objective_payload
        )

        objective_data[objective] = objective_payload

    # ------------------------------------------------------------------
    # Determine overall status
    # ------------------------------------------------------------------

    successful_objectives = [
        objective
        for objective, data in objective_data.items()
        if data.get("success") is True
    ]

    failed_objectives = [
        objective
        for objective, data in objective_data.items()
        if data.get("success") is not True
    ]

    if not requested_objectives:
        status = "no_objectives"
        success = False

    elif successful_objectives:
        # At least one requested objective succeeded.
        status = "ready"
        success = True

    else:
        # Every requested objective failed.
        status = "error"
        success = False

    # ------------------------------------------------------------------
    # Canonical payload
    # ------------------------------------------------------------------

    payload = {
        "status": status,
        "success": success,

        "client": {
            "id": resolved_client.get("id"),
            "code": resolved_client.get(
                "client_code"
            ),
            "name": resolved_client.get(
                "client_name"
            ),

            "ads_platforms": (
                (
                    resolved_client.get(
                        "ads_configuration"
                    )
                    or {}
                ).get(
                    "platforms",
                    [],
                )
                if isinstance(
                    resolved_client.get(
                        "ads_configuration"
                    ),
                    dict,
                )
                else []
            ),

            "meta_ad_accounts": (
                resolved_client.get(
                    "meta_ad_accounts",
                    [],
                )
            ),
        },

        "period": {
            "id": resolved_period.get("id"),

            "label": (
                resolved_period.get(
                    "period_label"
                )
                or resolved_period.get(
                    "label"
                )
            ),

            "start": resolved_period.get(
                "period_start"
            ),

            "end": resolved_period.get(
                "period_end"
            ),
        },

        "analysis_type": analysis_type,

        "platform_scope": scope,

        "objectives": requested_objectives,

        "objective_data": objective_data,

        "source": {
            "type": resolved_period.get(
                "active_source"
            ),
            "import_id": resolved_period.get(
                "import_id"
            ),
            "updated_at": (
                resolved_period.get(
                    "sync_completed_at"
                )
                or resolved_period.get(
                    "imported_at"
                )
            ),
        },

        "warnings": warnings,

        "summary": {},

        "rows": [],

        "display_metrics": [],

        "available_filters": {},

        "breakdowns": {},

        "unconfirmed_count": sum(
            int(
                data.get(
                    "unconfirmed_count",
                    0,
                )
                or 0
            )
            for data in objective_data.values()
        ),
    }

    return payload
