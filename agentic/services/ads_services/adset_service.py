from __future__ import annotations

from typing import Any

from agentic.config.dashboard_integration import AdsDashboardApiClient


class AdSetAdsService:

    OBJECTIVE_ALIASES = {
        "linkclicks": "link_clicks",
    }

    def __init__(
        self,
        api_client: AdsDashboardApiClient,
    ) -> None:
        self.api = api_client

    def retrieve(
        self,
        client_code: str,
        period_id: str,
        platform: str,
        objective: str,
        campaign_ids: list[str] | None = None,
        adset_ids: list[str] | None = None,
    ) -> dict[str, Any]:

        requested_objective = objective.lower().strip()
        objective_key = self.OBJECTIVE_ALIASES.get(
            requested_objective,
            requested_objective,
        )

        # Resolve client_code -> client UUID
        # Resolve period_id -> period UUID
        client, period = self.api.resolve_client_and_period(
            client_code=client_code,
            period_id=period_id,
        )

        client_id = str(client["id"])
        resolved_period_id = str(period["id"])

        # Retrieve data from dashboard API
        raw_data = self.api.get_adset_performance(
            client_id=client_id,
            period_id=resolved_period_id,
            platform_scope=platform,
            objective=objective_key,
            campaign_ids=campaign_ids,
            adset_ids=adset_ids,
        )

        creative_data = self.api.get_creative_performance(
            client_id=client_id,
            period_id=resolved_period_id,
            platform_scope=platform,
            objective=objective_key,
            campaign_ids=campaign_ids,
            adset_ids=adset_ids,
        )

        return {
            "analysis_type": "adset",
            "platform": platform,
            "client_code": client_code,
            "period_id": period_id,
            "objective": objective_key,
            "objective_data": self._build_objective_data(
                raw_data=raw_data,
                creative_data=creative_data,
                objective=objective_key,
            ),
        }

    def _build_objective_data(
        self,
        raw_data: dict[str, Any],
        creative_data: dict[str, Any],
        objective: str,
    ) -> dict[str, Any]:
        adsets = list(raw_data.get("rows") or [])
        source = raw_data.get("source") or {}
        creative_source = creative_data.get("source") or {}
        warnings = list(raw_data.get("warnings") or [])

        same_snapshot = (
            source.get("import_id")
            and source.get("import_id") == creative_source.get("import_id")
        )
        if not same_snapshot:
            warnings.append(
                "Creative breakdown was omitted because it does not use the same active snapshot as the Ad Set overview."
            )

        creatives_by_adset: dict[str, list[dict[str, Any]]] = {}
        if same_snapshot:
            for creative in creative_data.get("rows") or []:
                adset_id = str(creative.get("adset_id") or "")
                if adset_id:
                    creatives_by_adset.setdefault(adset_id, []).append(creative)

        campaigns: dict[str, dict[str, Any]] = {}
        breakdowns: dict[str, dict[str, Any]] = {}
        for adset in adsets:
            adset_id = str(adset.get("id") or "")
            if not adset_id:
                continue
            campaign_id = str(
                adset.get("campaign_id")
                or adset.get("campaign_name")
                or "unknown"
            )
            campaign = campaigns.setdefault(
                campaign_id,
                {
                    "id": adset.get("campaign_id"),
                    "name": adset.get("campaign_name"),
                    "adsets": [],
                },
            )
            campaign["adsets"].append(adset)
            breakdowns[adset_id] = {
                "adset": adset,
                "summary": adset.get("metrics") or {},
                "creatives": creatives_by_adset.get(adset_id, []),
                "display_metrics": creative_data.get("display_metrics") or raw_data.get("display_metrics") or [],
                "source": creative_source if same_snapshot else source,
                "warnings": [] if same_snapshot else [warnings[-1]],
            }

        return {
            "objective": objective,

            # Overall performance
            "objective_overview": {
                "summary": raw_data.get("summary") or {},
                "kpi": raw_data.get("kpi") or {},
                "campaigns": list(campaigns.values()),
                "adsets": adsets,
            },

            # Ad set level performance
            "adset_breakdowns": breakdowns,

            # Additional metadata
            "display_metrics": raw_data.get(
                "display_metrics",
                [],
            ),

            "kpi": raw_data.get(
                "kpi",
                {},
            ),

            "data_status": raw_data.get(
                "data_status",
            ),

            "source": source,
            "warnings": warnings,
        }
