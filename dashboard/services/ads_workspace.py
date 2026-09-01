from __future__ import annotations


ADS_PLATFORM_KEYS = ("instagram", "facebook", "google_sem", "google_gdn", "youtube", "tiktok")
DEFAULT_ADS_PLATFORMS = ADS_PLATFORM_KEYS
GOAL_TARGET_FIELDS = (
    "target_monthly",
    "budget_monthly",
    "target_cost_per_result",
)

ADS_GOAL_DEFINITIONS = {
    "instagram": (
        {"key": "reach", "label": "Reach", "family": "awareness", "source_metric": "reach"},
        {"key": "engagement", "label": "Engagement", "family": "engagement", "source_metric": "actions:post_interaction_gross"},
        {"key": "views", "label": "Views", "family": "awareness", "source_metric": "video_views"},
        {"key": "link_clicks", "label": "Link Clicks", "family": "traffic", "source_metric": "link_clicks"},
        {"key": "leads", "label": "Leads", "family": "conversion", "source_metric": "leads"},
    ),
    "facebook": (
        {"key": "reach", "label": "Reach", "family": "awareness", "source_metric": "reach"},
        {"key": "engagement", "label": "Engagement", "family": "engagement", "source_metric": "actions:post_interaction_gross"},
        {"key": "views", "label": "Views", "family": "awareness", "source_metric": "video_views"},
        {"key": "link_clicks", "label": "Link Clicks", "family": "traffic", "source_metric": "link_clicks"},
        {"key": "leads", "label": "Leads", "family": "conversion", "source_metric": "leads"},
    ),
    "google_sem": (
        {"key": "performance", "label": "Performance", "family": "traffic", "source_metric": "clicks"},
    ),
    "google_gdn": (
        {"key": "performance", "label": "Performance", "family": "traffic", "source_metric": "clicks"},
    ),
    "youtube": (
        {"key": "impressions", "label": "Impressions", "family": "awareness", "source_metric": "impressions"},
        {"key": "video_views", "label": "Video Views", "family": "awareness", "source_metric": "video_views"},
    ),
    "tiktok": (
        {"key": "reach", "label": "Reach", "family": "awareness", "source_metric": "reach"},
        {"key": "views", "label": "Views", "family": "awareness", "source_metric": "video_views"},
        {"key": "traffic", "label": "Traffic", "family": "traffic", "source_metric": "destination_clicks"},
        {"key": "community_interaction", "label": "Community Interaction", "family": "community", "source_metric": "paid_follows"},
        {"key": "leads", "label": "Leads", "family": "conversion", "source_metric": "leads"},
    ),
}

LEGACY_ADS_GOAL_DEFINITIONS = {
    "instagram": (
        {"key": "profile_visits", "label": "Profile Visits", "family": "profile_growth", "source_metric": "profile_visit_view"},
    ),
    "facebook": (
        {"key": "page_likes", "label": "Page Likes", "family": "profile_growth", "source_metric": "page_like|profile_visit_view"},
    ),
}

ADS_PLATFORM_DEFINITIONS = (
    {
        "key": "instagram",
        "label": "Instagram",
        "source": "meta",
        "source_label": "Meta Ads",
        "ingestion_status": "available",
        "storage_status": "available",
    },
    {
        "key": "facebook",
        "label": "Facebook",
        "source": "meta",
        "source_label": "Meta Ads",
        "ingestion_status": "available",
        "storage_status": "available",
    },
    {
        "key": "google_sem",
        "label": "Google SEM",
        "source": "google_ads",
        "source_label": "Google Ads",
        "ingestion_status": "coming_soon",
        "storage_status": "not_created",
    },
    {
        "key": "google_gdn",
        "label": "Google Display Network",
        "source": "google_ads",
        "source_label": "Google Ads",
        "ingestion_status": "coming_soon",
        "storage_status": "not_created",
    },
    {
        "key": "youtube",
        "label": "YouTube",
        "source": "google_ads",
        "source_label": "Google Ads",
        "ingestion_status": "coming_soon",
        "storage_status": "not_created",
    },
    {
        "key": "tiktok",
        "label": "TikTok",
        "source": "tiktok_ads",
        "source_label": "TikTok Ads",
        "ingestion_status": "coming_soon",
        "storage_status": "not_created",
    },
)


def normalize_ads_platforms(value, *, use_default: bool = True) -> list[str]:
    if isinstance(value, dict):
        value = value.get("platforms", value.get("ads_platforms"))
    if value is None:
        value = DEFAULT_ADS_PLATFORMS if use_default else ()
    if not isinstance(value, (list, tuple, set)):
        raise ValueError("Ads platforms must be a list.")
    requested = {str(item).strip().lower() for item in value if str(item).strip()}
    unsupported = sorted(requested.difference(ADS_PLATFORM_KEYS))
    if unsupported:
        raise ValueError(f"Unsupported Ads platforms: {', '.join(unsupported)}")
    ordered = [platform for platform in ADS_PLATFORM_KEYS if platform in requested]
    if not ordered:
        raise ValueError("Select at least one Ads platform.")
    return ordered


def normalize_meta_ad_account_ids(value) -> list[str]:
    if isinstance(value, dict):
        value = value.get("meta_ad_account_ids", [])
    if value is None:
        return []
    if not isinstance(value, (list, tuple, set)):
        raise ValueError("Meta Ad Accounts must be a list.")
    result = []
    for item in value:
        account_id = str(item or "").strip()
        if not account_id:
            continue
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        if account_id not in result:
            result.append(account_id)
    return result


def _number_or_none(value, field: str):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if number < 0:
        raise ValueError(f"{field} cannot be negative.")
    return int(number) if number.is_integer() else number


def normalize_ads_goals(
    value,
    platforms: list[str],
    *,
    use_default: bool = True,
) -> dict[str, list[dict]]:
    raw_goals = None
    if isinstance(value, dict):
        raw_goals = value.get("goals", value.get("ads_goals"))
    result = {}
    for platform in platforms:
        definitions = ADS_GOAL_DEFINITIONS[platform]
        legacy_definitions = LEGACY_ADS_GOAL_DEFINITIONS.get(platform, ())
        allowed = {item["key"]: item for item in (*definitions, *legacy_definitions)}
        selected = raw_goals.get(platform, []) if isinstance(raw_goals, dict) else None
        if selected is None and use_default:
            selected = [item["key"] for item in definitions]
        elif selected is None:
            selected = []
        if not isinstance(selected, (list, tuple)):
            raise ValueError(f"Ads goals for {platform} must be a list.")
        normalized = []
        seen = set()
        for item in selected:
            payload = item if isinstance(item, dict) else {"key": item}
            key = str(payload.get("key") or "").strip().lower()
            if key not in allowed:
                raise ValueError(f"Unsupported {platform} Ads goal: {key or '(empty)'}")
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                "key": key,
                **{
                    field: _number_or_none(payload.get(field), field)
                    for field in GOAL_TARGET_FIELDS
                },
            })
        result[platform] = normalized
    if not any(result.values()):
        raise ValueError("Select at least one Ads goal for this report month.")
    return result


def ads_product_configuration(value=None) -> dict:
    configuration = {"platforms": normalize_ads_platforms(value)}
    if isinstance(value, dict) and "meta_ad_account_ids" in value:
        configuration["meta_ad_account_ids"] = normalize_meta_ad_account_ids(value)
    return configuration


def ads_period_configuration(value=None, platforms=None) -> dict:
    configured_platforms = normalize_ads_platforms(platforms)
    return {
        "goals": normalize_ads_goals(
            value,
            configured_platforms,
            use_default=value is None or not value,
        )
    }


def ads_platform_catalog(configured_platforms=None, period_configuration=None) -> list[dict]:
    product_configuration = ads_product_configuration(configured_platforms)
    configured = set(product_configuration["platforms"])
    active_goals = (
        ads_period_configuration(
            period_configuration,
            product_configuration["platforms"],
        )["goals"]
        if period_configuration is not None
        else {}
    )
    return [
        {
            **definition,
            "configured": definition["key"] in configured,
            "goals": [
                {
                    **goal,
                    "active": any(
                        item["key"] == goal["key"]
                        for item in active_goals.get(definition["key"], [])
                    ),
                }
                for goal in (
                    *ADS_GOAL_DEFINITIONS[definition["key"]],
                    *LEGACY_ADS_GOAL_DEFINITIONS.get(definition["key"], ()),
                )
            ],
            "active_goals": active_goals.get(definition["key"], []),
        }
        for definition in ADS_PLATFORM_DEFINITIONS
    ]
