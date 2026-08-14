from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from typing import Any

import requests


class MetaAdsApiError(RuntimeError):
    """A safe-to-display Meta API error (never includes the access token)."""

    def __init__(self, message: str, *, code: int | None = None, status: int = 502):
        super().__init__(message)
        self.code = code
        self.status = status


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _actions(row: dict) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in row.get("actions") or []:
        key = str(item.get("action_type") or "").lower()
        if key:
            result[key] = result.get(key, 0) + _number(item.get("value"))
    return result


def _action_value(actions: dict[str, float], aliases: tuple[str, ...]) -> float:
    return sum(actions.get(alias, 0) for alias in aliases)


def _instagram_profile_visits(row: dict, actions: dict[str, float]) -> float:
    direct = row.get("instagram_profile_visits")
    if direct is not None:
        return _number(direct)
    return _action_value(
        actions,
        (
            "profile_visit",
            "profile_visit_view",
            "instagram_profile_visit",
            "onsite_conversion.instagram_profile_visit",
        ),
    )


def _facebook_page_likes(actions: dict[str, float]) -> float:
    # In MAI reporting, Facebook Page Likes occupies the same profile-growth
    # goal slot as Instagram Profile Visits. Meta/CSV exports may label that
    # Facebook result as either a page-like or a profile/page visit.
    return _action_value(
        actions,
        (
            "page_like",
            "page_likes",
            "actions:page_like",
            "profile_visit",
            "profile_visit_view",
            "facebook_profile_visit",
            "onsite_conversion.page_like",
        ),
    )


def _hash_key(*values: Any) -> str:
    return hashlib.sha256("|".join(str(value or "") for value in values).encode()).hexdigest()


class MetaAdsApiClient:
    def __init__(
        self,
        access_token: str | None = None,
        api_version: str | None = None,
        *,
        session=None,
        timeout: int | None = None,
        max_retries: int = 2,
    ):
        self.access_token = access_token or os.getenv("META_ADS_ACCESS_TOKEN", "")
        self.api_version = api_version or os.getenv("META_API_VERSION", "v23.0")
        self.timeout = timeout or int(os.getenv("META_ADS_API_TIMEOUT", "30"))
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    @property
    def configured(self) -> bool:
        return bool(self.access_token.strip())

    def _get(self, path_or_url: str, params: dict | None = None) -> dict:
        if not self.configured:
            raise MetaAdsApiError("META_ADS_ACCESS_TOKEN is not configured.", status=503)
        url = path_or_url if path_or_url.startswith("https://") else f"{self.base_url}/{path_or_url.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise MetaAdsApiError("Could not connect to Meta Ads API.") from exc
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            error = payload.get("error") if isinstance(payload, dict) else None
            if response.status_code < 400 and not error:
                return payload
            code = error.get("code") if isinstance(error, dict) else None
            transient = response.status_code == 429 or response.status_code >= 500 or code in {1, 2, 4, 17, 32, 613}
            if transient and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 0.25 * (2**attempt))
                continue
            message = error.get("message") if isinstance(error, dict) else None
            safe = "Meta permission was denied." if response.status_code in {401, 403} or code in {10, 190, 200} else "Meta Ads API request failed."
            if message and "permission" in message.lower():
                safe = "Meta permission was denied for this resource."
            raise MetaAdsApiError(safe, code=code, status=401 if code == 190 else 502)
        raise MetaAdsApiError("Meta Ads API request failed.")

    def _all(self, path: str, params: dict | None = None) -> list[dict]:
        rows: list[dict] = []
        payload = self._get(path, params)
        while True:
            rows.extend(payload.get("data") or [])
            next_url = (payload.get("paging") or {}).get("next")
            if not next_url:
                return rows
            payload = self._get(next_url)

    def status(self) -> dict:
        if not self.configured:
            return {"configured": False, "valid": False, "permissions": []}
        try:
            identity = self._get("me", {"fields": "id,name"})
            permissions = self._all("me/permissions")
            return {
                "configured": True,
                "valid": True,
                "identity": {"id": identity.get("id"), "name": identity.get("name")},
                "permissions": permissions,
            }
        except MetaAdsApiError as exc:
            return {"configured": True, "valid": False, "permissions": [], "error": str(exc)}

    def ad_accounts(self) -> list[dict]:
        fields = "id,account_id,name,account_status,currency,timezone_name,timezone_offset_hours_utc"
        rows = self._all("me/adaccounts", {"fields": fields, "limit": 200})
        return [
            {
                "id": row.get("id") or f"act_{row.get('account_id')}",
                "account_id": row.get("account_id"),
                "name": row.get("name") or "Unnamed Ad Account",
                "account_status": row.get("account_status"),
                "currency": row.get("currency"),
                "timezone_name": row.get("timezone_name"),
                "timezone_offset_hours_utc": row.get("timezone_offset_hours_utc"),
                "is_active": row.get("account_status") == 1,
            }
            for row in rows
        ]

    def _entities(self, account_id: str) -> tuple[dict, dict, dict, list[dict]]:
        campaigns = self._all(
            f"{account_id}/campaigns",
            {"fields": "id,name,objective,effective_status,start_time,stop_time", "limit": 200},
        )
        adsets = self._all(
            f"{account_id}/adsets",
            {"fields": "id,name,campaign_id,optimization_goal,effective_status,start_time,end_time,bid_strategy,daily_budget,lifetime_budget", "limit": 200},
        )
        ads = self._all(
            f"{account_id}/ads",
            {"fields": "id,name,campaign_id,adset_id,effective_status,creative{id,name,thumbnail_url,image_url,effective_object_story_id,object_story_spec}", "limit": 200},
        )
        return (
            {row["id"]: row for row in campaigns},
            {row["id"]: row for row in adsets},
            {row["id"]: row for row in ads},
            ads,
        )

    def _insights(self, account_id: str, start: date, end: date, *, level="ad", breakdowns=None) -> list[dict]:
        fields = (
            "account_id,account_name,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,"
            "reach,impressions,frequency,spend,clicks,inline_link_clicks,ctr,cpc,cpm,actions,"
            "cost_per_action_type,instagram_profile_visits,instagram_profile_follow,date_start,date_stop"
        )
        params = {
            "level": level,
            "fields": fields,
            "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
            "time_increment": "all_days",
            "limit": 500,
        }
        if breakdowns:
            params["breakdowns"] = ",".join(breakdowns)
        return self._all(f"{account_id}/insights", params)

    def fetch_account_snapshot(self, account: dict, start: date, end: date, platforms: list[str], goals: dict) -> dict:
        account_id = account["id"]
        campaign_meta, adset_meta, ad_meta, raw_ads = self._entities(account_id)
        level_rows = {level: self._insights(account_id, start, end, level=level) for level in ("campaign", "adset", "ad")}
        placement_rows = self._insights(account_id, start, end, breakdowns=["publisher_platform", "platform_position", "impression_device"])
        demographic_rows = self._insights(account_id, start, end, breakdowns=["age", "gender"])
        region_rows = self._insights(account_id, start, end, breakdowns=["region"])

        def normalized(row: dict, row_number: int, result_type: str, result_value: float, scope_platform: str) -> dict:
            actions = _actions(row)
            campaign = campaign_meta.get(str(row.get("campaign_id"))) or {}
            adset = adset_meta.get(str(row.get("adset_id"))) or {}
            ad = ad_meta.get(str(row.get("ad_id"))) or {}
            reach = _number(row.get("reach"))
            impressions = _number(row.get("impressions"))
            spend = _number(row.get("spend"))
            engagements = _action_value(actions, ("post_engagement", "post_interaction_gross"))
            link_clicks = _number(row.get("inline_link_clicks")) or _action_value(actions, ("link_click", "outbound_click"))
            return {
                "meta_ad_account_id": account_id,
                "campaign_external_id": row.get("campaign_id"), "campaign_name": row.get("campaign_name") or campaign.get("name") or "Unnamed campaign",
                "adset_external_id": row.get("adset_id"), "adset_name": row.get("adset_name") or adset.get("name") or "Unnamed ad set",
                "ad_external_id": row.get("ad_id"), "ad_name": row.get("ad_name") or ad.get("name") or "Unnamed ad",
                "source_row_key": _hash_key(account_id, scope_platform, row.get("campaign_id"), row.get("adset_id"), row.get("ad_id"), row.get("publisher_platform"), row.get("platform_position"), row.get("impression_device"), row.get("age"), row.get("gender"), row.get("region"), result_type),
                "source_row_number": row_number, "reporting_start": row.get("date_start") or start, "reporting_end": row.get("date_stop") or end,
                "delivery_status": ad.get("effective_status") or adset.get("effective_status") or campaign.get("effective_status"),
                "result_value": result_value, "result_type": result_type, "cost_per_result": spend / result_value if result_value else None,
                "spend": spend, "impressions": impressions, "reach": reach, "frequency": _number(row.get("frequency")) or (impressions / reach if reach else None),
                "post_engagements": engagements, "link_clicks": link_clicks, "link_ctr": link_clicks / impressions * 100 if impressions else None,
                "instagram_follows": _number(row.get("instagram_profile_follow")) or _action_value(actions, ("follow", "instagram_profile_follow")),
                "page_engagements": _action_value(actions, ("page_engagement",)),
                "publisher_platform": row.get("publisher_platform"), "placement": row.get("platform_position"), "device_platform": row.get("impression_device"),
                "age": row.get("age"), "gender": row.get("gender"), "region": row.get("region"),
                "raw_data": {**row, "campaign_objective": campaign.get("objective"), "optimization_goal": adset.get("optimization_goal")},
            }

        goal_specs = []
        for platform in platforms:
            for goal in goals.get(platform, []):
                key = goal.get("key") if isinstance(goal, dict) else goal
                goal_specs.append((platform, key))

        def result_for(row: dict, platform: str, goal: str) -> tuple[str, float]:
            actions = _actions(row)
            if goal == "reach": return "reach", _number(row.get("reach"))
            if goal == "engagement": return "post_engagement", _action_value(actions, ("post_engagement", "post_interaction_gross"))
            if goal == "profile_visits": return "profile_visit", _instagram_profile_visits(row, actions)
            if goal == "page_likes": return "page_like", _facebook_page_likes(actions)
            return str(goal), 0

        datasets: dict[str, list[dict]] = {key: [] for key in ("campaign", "adset", "ad", "placement", "demographic", "region")}
        for kind, rows in level_rows.items():
            for index, row in enumerate(rows, 1):
                for platform, goal in goal_specs:
                    result_type, value = result_for(row, platform, goal)
                    datasets[kind].append(normalized(row, index, result_type, value, platform))
        for kind, rows in (("placement", placement_rows), ("demographic", demographic_rows), ("region", region_rows)):
            for index, row in enumerate(rows, 1):
                publisher = str(row.get("publisher_platform") or "").lower()
                breakdown_goals = goal_specs if kind == "placement" else [("shared", goal) for goal in dict.fromkeys(goal for _platform, goal in goal_specs)]
                for platform, goal in breakdown_goals:
                    if kind == "placement" and publisher and publisher != platform:
                        continue
                    result_type, value = result_for(row, platform, goal)
                    item = normalized(row, index, result_type, value, platform)
                    if kind != "placement":
                        item["publisher_platform"] = platform
                    datasets[kind].append(item)

        fetched_at = datetime.now(timezone.utc)
        creatives = []
        for ad in raw_ads:
            creative = ad.get("creative") or {}
            story_spec = creative.get("object_story_spec") or {}
            link_data = story_spec.get("link_data") or {}
            video_data = story_spec.get("video_data") or {}
            creatives.append({
                "meta_ad_account_id": account_id, "campaign_external_id": ad.get("campaign_id"), "adset_external_id": ad.get("adset_id"),
                "ad_external_id": ad.get("id"), "creative_external_id": creative.get("id"), "creative_name": creative.get("name"),
                "thumbnail_url": creative.get("thumbnail_url") or video_data.get("image_url"), "image_url": creative.get("image_url") or link_data.get("picture"),
                "preview_url": None, "permalink_url": link_data.get("link"), "effective_object_story_id": creative.get("effective_object_story_id"),
                "page_id": story_spec.get("page_id"), "instagram_actor_id": story_spec.get("instagram_actor_id"),
                "creative_fetched_at": fetched_at, "raw_data": ad,
            })
        return {"datasets": datasets, "creatives": creatives}


class MetaAdsSyncService:
    def __init__(self, repository, api_client: MetaAdsApiClient | None = None):
        self.repository = repository
        self.api = api_client or MetaAdsApiClient()

    def sync(self, client_id: str, period_id: str, payload: dict) -> dict:
        platforms = [str(item).lower() for item in payload.get("platforms") or []]
        if not platforms or any(item not in {"instagram", "facebook"} for item in platforms):
            raise ValueError("Select Instagram, Facebook, or both.")
        account_ids = [str(item) for item in payload.get("ad_account_ids") or []]
        if not account_ids:
            raise ValueError("Select at least one Meta Ad Account.")
        context = self.repository.sync_context(client_id, period_id, account_ids, payload.get("goals"))
        currencies = {account.get("currency") for account in context["accounts"] if account.get("currency")}
        if len(currencies) > 1:
            raise ValueError("Selected Ad Accounts use different currencies and cannot be aggregated.")
        timezones = sorted({account.get("timezone_name") for account in context["accounts"] if account.get("timezone_name")})
        warnings = []
        if len(timezones) > 1:
            warnings.append("Selected accounts use different timezones: " + ", ".join(timezones))
        import_id = self.repository.start_api_snapshot(client_id, period_id, account_ids, platforms, warnings)
        datasets = {key: [] for key in ("campaign", "adset", "ad", "placement", "demographic", "region")}
        creatives = []
        try:
            for account in context["accounts"]:
                fetched = self.api.fetch_account_snapshot(account, context["period_start"], context["period_end"], platforms, context["goals"])
                for key in datasets:
                    datasets[key].extend(fetched["datasets"][key])
                creatives.extend(fetched["creatives"])
            return self.repository.complete_api_snapshot(import_id, client_id, period_id, platforms, datasets, creatives, warnings)
        except Exception as exc:
            self.repository.fail_api_snapshot(import_id, str(exc))
            raise
