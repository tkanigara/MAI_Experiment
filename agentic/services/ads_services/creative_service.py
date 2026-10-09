from __future__ import annotations

from typing import Any

from agentic.config.dashboard_integration import AdsDashboardApiClient


class CreativeAdsService:

    OBJECTIVE_ALIASES = {
        "linkclicks": "link_clicks",
        "profilevisit": "profile_visits",
        "profile_visit": "profile_visits",
        "pagelike": "page_likes",
        "page_like": "page_likes",
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
    ) -> dict[str, Any]:

        client, period = self.api.resolve_client_and_period(
            client_code=client_code,
            period_id=period_id,
        )

        client_id = str(client["id"])
        resolved_period_id = str(period["id"])

        requested_objective = objective.lower().strip()
        objective_key = self.OBJECTIVE_ALIASES.get(
            requested_objective,
            requested_objective,
        )

        raw_data = self.api.get_creative_performance(
            client_id=client_id,
            period_id=resolved_period_id,
            platform_scope=platform,
            objective=objective_key,
            campaign_ids=campaign_ids,
        )

        objective_data = self._build_objective_data(
            raw_data=raw_data,
            objective=objective_key,
        )

        return {
            "analysis_type": "creative",
            "platform": platform,
            "client_code": client_code,
            "period_id": period_id,
            "objective": objective_key,
            "objective_data": objective_data,
        }

    def _build_objective_data(
        self,
        raw_data: dict[str, Any],
        objective: str,
    ) -> dict[str, Any]:

        rows = raw_data.get("rows", [])
        summary = raw_data.get("summary", {})
        display_metrics = raw_data.get("display_metrics", [])
        kpi = raw_data.get("kpi", {})
        available_filters = raw_data.get("available_filters", {})
        warnings = raw_data.get("warnings", [])

        return {
            "performance_overview": {
                "objective": objective,
                "summary": summary,
                "display_metrics": display_metrics,
                "kpi": kpi,
            },

            "content_analysis": {
                "creatives": rows,
            },

            "creative_comparison": {
                "creatives": rows,
                "comparison_metrics": display_metrics,
            },

            "top_creatives": {
                "creatives": self._get_top_creatives(
                    rows=rows,
                    objective=objective,
                ),
            },

            "available_filters": available_filters,
            "warnings": warnings,
        }

    def _get_top_creatives(
        self,
        rows: list[dict[str, Any]],
        objective: str,
    ) -> list[dict[str, Any]]:

        if not rows:
            return []

        metric_map = {
            "reach": "reach",
            "engagement": "post_engagements",
            "link_clicks": "link_clicks",
            "leads": "leads",
            "views": "views",
            "profile_visits": "profile_visits",
            "page_likes": "page_likes",
        }

        metric = metric_map.get(objective)

        if not metric:
            return rows[:5]

        valid_rows = []

        for row in rows:
            metrics = row.get("metrics", {})

            value = metrics.get(metric)

            if value is None:
                continue

            valid_rows.append(row)

        valid_rows.sort(
            key=lambda row: row.get("metrics", {}).get(metric, 0) or 0,
            reverse=True,
        )

        return valid_rows[:5]

    def retrieve_metadata(
        self,
        client_code: str,
        period_id: str,
    ) -> dict[str, Any]:

        # Use centralized resolver
        client, period = self.api.resolve_client_and_period(
            client_code=client_code,
            period_id=period_id,
        )

        client_id = str(client["id"])

        return {
            "client_id": client_id,
            "client_code": client.get("client_code"),
            "client_name": client.get("client_name"),

            "report_period_id": period.get("id"),
            "period_start": period.get("period_start"),
            "period_end": period.get("period_end"),

            "instagram": client.get(
                "instagram",
                False,
            ),
            "facebook": client.get(
                "facebook",
                False,
            ),
            "tiktok": client.get(
                "tiktok",
                False,
            ),
            "youtube": client.get(
                "youtube",
                False,
            ),
            "linkedin": client.get(
                "linkedin",
                False,
            ),
            "threads": client.get(
                "threads",
                False,
            ),

            "ads_platforms": client.get(
                "ads_platforms",
                [],
            ),

            "meta_ad_accounts": client.get(
                "meta_ad_accounts",
                [],
            ),

            "source": {
                "system": "ads_dashboard",
            },

            "warnings": [],
            "loaded": True,
            "error": None,
        }
