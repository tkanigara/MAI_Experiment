from __future__ import annotations
from typing import Any, Mapping
import os
from dataclasses import dataclass

import requests

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
            timeout_seconds=float(
                os.getenv("ADS_DASHBOARD_API_TIMEOUT", "15")
            ),
        )


class AdsDashboardApiClientError(RuntimeError):
    pass

class AdsDashboardApiClient:

    def __init__(
        self,
        config: DashboardClientConfig | None = None,
        session: requests.Session | Any | None = None,
    ) -> None:
        self.config = config or DashboardClientConfig.from_env()
        self.session = session or requests.Session()

    # =========================================================
    # BASE HTTP CLIENT
    # =========================================================

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> Any:

        url = f"{self.config.base_url}/{path.lstrip('/')}"

        try:
            response = self.session.get(
                url,
                params=dict(params or {}),
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AdsDashboardApiClientError(
                "The Ads dashboard could not be reached."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AdsDashboardApiClientError(
                f"Invalid dashboard response "
                f"(HTTP {response.status_code})."
            ) from exc

        if response.status_code >= 400:
            raise AdsDashboardApiClientError(
                f"Dashboard request failed "
                f"(HTTP {response.status_code}): "
                f"{payload}"
            )

        return payload

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _as_list(
        payload: Any,
        key: str,
    ) -> list[dict[str, Any]]:
        """
        Normalize dashboard responses into a list of dictionaries.

        Supports:
        - [...]
        - {"clients": [...]}
        - {"periods": [...]}
        """

        if isinstance(payload, list):
            return [
                item
                for item in payload
                if isinstance(item, dict)
            ]

        if isinstance(payload, dict):
            value = payload.get(key, [])

            if isinstance(value, list):
                return [
                    item
                    for item in value
                    if isinstance(item, dict)
                ]

        return []

    # =========================================================
    # CLIENT
    # =========================================================

    def get_clients(
        self,
        product: str = "meta_ads",
    ) -> Any:
        return self.get(
            "/api/clients",
            {
                "product": product,
            },
        )

    # =========================================================
    # PERIOD
    # =========================================================

    def get_periods(
        self,
        client_id: str,
    ) -> Any:
        """
        Retrieve periods using the internal client UUID.

        NOTE:
        Backend endpoint expects client_id, not client_code.
        """

        return self.get(
            f"/api/ads/clients/{client_id}/periods"
        )

    # =========================================================
    # CLIENT + PERIOD RESOLUTION
    # =========================================================

    def resolve_client_and_period(
        self,
        client_code: str,
        period_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Resolve user-facing identifiers into dashboard UUIDs.

        Input:
            client_code = "jba"
            period_id   = "2026-08-01"

        Output:
            client = {
                ...
                "id": "<client UUID>"
            }

            period = {
                ...
                "id": "<period UUID>"
            }
        """

        # -----------------------------------------------------
        # 1. Resolve client_code -> client UUID
        # -----------------------------------------------------

        clients_payload = self.get_clients()

        clients = self._as_list(
            clients_payload,
            "clients",
        )

        client = next(
            (
                item
                for item in clients
                if str(item.get("client_code", "")).lower()
                == str(client_code).lower()
            ),
            None,
        )

        if not client:
            raise AdsDashboardApiClientError(
                f"Ads client '{client_code}' was not found."
            )

        client_id = client.get("id")

        if not client_id:
            raise AdsDashboardApiClientError(
                f"Ads client '{client_code}' does not contain an id."
            )

        # -----------------------------------------------------
        # 2. Resolve period using client UUID
        # -----------------------------------------------------

        periods_payload = self.get_periods(
            client_id=str(client_id)
        )

        periods = self._as_list(
            periods_payload,
            "periods",
        )

        requested_period = str(period_id)

        period = next(
            (
                item
                for item in periods
                if (
                    str(item.get("id", ""))
                    == requested_period
                )
                or (
                    str(item.get("period_start", ""))[:10]
                    == requested_period[:10]
                )
            ),
            None,
        )

        if not period:
            raise AdsDashboardApiClientError(
                f"Period '{period_id}' was not found "
                f"for client '{client_code}'."
            )

        period_uuid = period.get("id")

        if not period_uuid:
            raise AdsDashboardApiClientError(
                f"Resolved period '{period_id}' does not contain an id."
            )

        return client, period

    # =========================================================
    # CREATIVE PERFORMANCE
    # =========================================================

    def get_creative_performance(
        self,
        client_id: str,
        period_id: str,
        platform_scope: str,
        objective: str | None = None,
        campaign_ids: list[str] | None = None,
        adset_ids: list[str] | None = None,
    ) -> Any:

        params: dict[str, Any] = {
            "platform_scope": platform_scope,
        }

        if objective:
            params["objective"] = objective

        if campaign_ids:
            params["campaign_ids"] = ",".join(
                campaign_ids
            )

        if adset_ids:
            params["adset_ids"] = ",".join(
                adset_ids
            )

        return self.get(
            f"/api/ads/clients/{client_id}"
            f"/periods/{period_id}"
            f"/creative-performance",
            params,
        )

    # =========================================================
    # AD SET PERFORMANCE
    # =========================================================

    def get_adset_performance(
        self,
        client_id: str,
        period_id: str,
        platform_scope: str,
        objective: str | None = None,
        campaign_ids: list[str] | None = None,
        adset_ids: list[str] | None = None,
    ) -> Any:

        params: dict[str, Any] = {
            "platform_scope": platform_scope,
        }

        if objective:
            params["objective"] = objective

        if campaign_ids:
            params["campaign_ids"] = ",".join(
                campaign_ids
            )

        if adset_ids:
            params["adset_ids"] = ",".join(
                adset_ids
            )

        return self.get(
            f"/api/ads/clients/{client_id}"
            f"/periods/{period_id}"
            f"/adset-performance",
            params,
        )

    # =========================================================
    # AD SET CREATIVES
    # =========================================================

    def get_adset_creatives(
        self,
        client_id: str,
        period_id: str,
        adset_id: str,
        platform_scope: str,
        objective: str | None = None,
    ) -> Any:

        params: dict[str, Any] = {
            "platform_scope": platform_scope,
        }

        if objective:
            params["objective"] = objective

        return self.get(
            f"/api/ads/clients/{client_id}"
            f"/periods/{period_id}"
            f"/adsets/{adset_id}/creatives",
            params,
        )
