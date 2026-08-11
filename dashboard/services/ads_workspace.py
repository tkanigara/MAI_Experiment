from __future__ import annotations


ADS_PLATFORM_KEYS = ("instagram", "facebook", "youtube", "tiktok")
DEFAULT_ADS_PLATFORMS = ADS_PLATFORM_KEYS

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
        value = value.get("platforms")
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


def ads_product_configuration(value=None) -> dict:
    return {"platforms": normalize_ads_platforms(value)}


def ads_platform_catalog(configured_platforms=None) -> list[dict]:
    configured = set(normalize_ads_platforms(configured_platforms))
    return [
        {**definition, "configured": definition["key"] in configured}
        for definition in ADS_PLATFORM_DEFINITIONS
    ]
