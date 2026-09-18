from __future__ import annotations

from typing import Any

from agentic.config.dashboard_integration import AdsDashboardApiClient


class AdSetAdsService:

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

        objective_key = objective.lower().strip()

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

        return {
            "analysis_type": "adset",
            "platform": platform,
            "client_code": client_code,
            "period_id": period_id,
            "objective": objective_key,
            "objective_data": self._build_objective_data(
                raw_data=raw_data,
                objective=objective_key,
            ),
        }

    def _build_objective_data(
        self,
        raw_data: dict[str, Any],
        objective: str,
    ) -> dict[str, Any]:

        return {
            "objective": objective,

            # Overall performance
            "objective_overview": raw_data.get(
                "summary",
                {},
            ),

            # Ad set level performance
            "adset_breakdowns": raw_data.get(
                "rows",
                [],
            ),

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

            "warnings": raw_data.get(
                "warnings",
                [],
            ),
        }
