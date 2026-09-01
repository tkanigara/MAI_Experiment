"""Small, testable client for the Ads dashboard API.

The dashboard remains the source of truth for Ads data.  Agents should not
reach into dashboard tables directly because the dashboard applies active
snapshot selection, objective mappings, metric configuration, and overrides
there.  This client deliberately exposes only the read paths needed by the
analysis workflow.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import requests


class AdsDashboardClientError(RuntimeError):
    """A safe, user-facing error returned by the dashboard API."""


@dataclass(frozen=True)
class DashboardClientConfig:
    base_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "DashboardClientConfig":
        return cls(
            base_url=(
                os.getenv("ADS_DASHBOARD_API_URL")
                or os.getenv("DASHBOARD_API_BASE_URL")
                or "http://127.0.0.1:8000"
            ).rstrip("/"),
            timeout_seconds=float(os.getenv("ADS_DASHBOARD_API_TIMEOUT", "15")),
        )


class AdsDashboardClient:
    """HTTP adapter for dashboard Ads retrieval endpoints.

    ``session`` is injectable so unit tests can use a fake response object
    without starting the dashboard server.
    """

    def __init__(
        self,
        config: DashboardClientConfig | None = None,
        session: requests.Session | Any | None = None,
    ) -> None:
        self.config = config or DashboardClientConfig.from_env()
        self.session = session or requests.Session()

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        try:
            response = self.session.get(
                url,
                params=dict(params or {}),
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AdsDashboardClientError(
                "The Ads dashboard could not be reached. Check that the dashboard server is running."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AdsDashboardClientError(
                f"The Ads dashboard returned an invalid response (HTTP {response.status_code})."
            ) from exc

        if response.status_code >= 400:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            message = str(detail or f"Dashboard request failed (HTTP {response.status_code}).")
            raise AdsDashboardClientError(message[:500])
        return payload

    @staticmethod
    def _as_list(payload: Any, key: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            value = payload.get(key, [])
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def resolve_client_and_period(
        self,
        client_code: str,
        period_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        clients_payload = self._get("/api/clients", {"product": "meta_ads"})
        clients = self._as_list(clients_payload, "clients")
        client = next(
            (
                item
                for item in clients
                if str(item.get("client_code", "")).lower() == str(client_code).lower()
            ),
            None,
        )
        if not client:
            raise AdsDashboardClientError(
                f"Ads client '{client_code}' was not found."
            )

        client_id = client.get("id")
        if not client_id:
            raise AdsDashboardClientError("The Ads client response did not contain an id.")

        periods_payload = self._get(f"/api/ads/clients/{client_id}/periods")
        periods = self._as_list(periods_payload, "periods")
        requested = str(period_id)
        period = next(
            (
                item
                for item in periods
                if str(item.get("id", "")) == requested
                or str(item.get("period_start", ""))[:10] == requested[:10]
            ),
            None,
        )
        if not period:
            raise AdsDashboardClientError(
                f"Report period '{period_id}' was not found for Ads client '{client_code}'."
            )
        return client, period

    def get_analysis(
        self,
        *,
        client_id: str,
        period_id: str,
        analysis_type: str,
        platform_scope: str,
        objective: str,
        campaign_ids: list[str] | None = None,
        adset_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dimension = str(analysis_type or "creative").strip().lower()
        if dimension not in {"creative", "adset"}:
            raise AdsDashboardClientError(
                "Ads analysis_type must be 'creative' or 'adset'."
            )
        path = (
            f"/api/ads/clients/{client_id}/periods/{period_id}/"
            f"{'creative-performance' if dimension == 'creative' else 'adset-performance'}"
        )
        return self._get(
            path,
            {
                "platform_scope": platform_scope or "meta",
                "objective": objective or "",
                "campaign_ids": ",".join(str(item) for item in (campaign_ids or [])),
                "adset_ids": ",".join(str(item) for item in (adset_ids or [])),
            },
        )

    def get_creative_detail(
        self,
        *,
        client_id: str,
        period_id: str,
        creative_id: str,
        platform_scope: str,
    ) -> dict[str, Any]:
        return self._get(
            f"/api/ads/clients/{client_id}/periods/{period_id}/creatives/{creative_id}",
            {"platform_scope": platform_scope or "meta"},
        )

    def get_adset_creatives(
        self,
        *,
        client_id: str,
        period_id: str,
        adset_id: str,
        platform_scope: str,
        objective: str,
    ) -> dict[str, Any]:
        return self._get(
            f"/api/ads/clients/{client_id}/periods/{period_id}/adsets/{adset_id}/creatives",
            {
                "platform_scope": platform_scope or "meta",
                "objective": objective or "",
            },
        )

