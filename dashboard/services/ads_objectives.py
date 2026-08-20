from __future__ import annotations

from copy import deepcopy


METRICS = {
    "result": {"label": "Results", "format": "number"},
    "reach": {"label": "Reach", "format": "number"},
    "impressions": {"label": "Impressions", "format": "number"},
    "post_engagements": {"label": "Post Engagements", "format": "number"},
    "interactions": {"label": "Interactions", "format": "number"},
    "post_shares": {"label": "Post Shares", "format": "number"},
    "post_saves": {"label": "Post Saves", "format": "number"},
    "post_reactions": {"label": "Post Reactions", "format": "number"},
    "post_comments": {"label": "Post Comments", "format": "number"},
    "link_clicks": {"label": "Link Clicks", "format": "number"},
    "destination_clicks": {"label": "Destination Clicks", "format": "number"},
    "frequency": {"label": "Frequency", "format": "decimal"},
    "ctr": {"label": "CTR", "format": "percentage", "formula": "link_clicks / impressions * 100"},
    "engagement_rate": {"label": "Engagement Rate", "format": "percentage", "formula": "post_engagements / impressions * 100"},
    "result_rate": {"label": "Result Rate", "format": "percentage", "formula": "result / impressions * 100"},
    "cost_per_result": {"label": "Cost per Result", "format": "currency", "formula": "spend / result"},
    "spend": {"label": "Spent", "format": "currency"},
    "video_views": {"label": "Video Views", "format": "number"},
    "video_views_2s": {"label": "2-Second Video Views", "format": "number"},
    "video_views_6s": {"label": "6-Second Video Views", "format": "number"},
    "thruplay": {"label": "ThruPlay Views", "format": "number"},
    "leads": {"label": "Leads", "format": "number"},
    "paid_follows": {"label": "Paid Follows", "format": "number"},
    "clicks": {"label": "Clicks", "format": "number"},
    "cpm": {"label": "CPM", "format": "currency", "formula": "spend / impressions * 1000"},
    "cpc": {"label": "CPC", "format": "currency", "formula": "spend / clicks"},
    "trueview_views": {"label": "TrueView Views", "format": "number"},
    "viewable_rate": {"label": "Viewable Rate", "format": "percentage"},
    "video_25": {"label": "Video Played to 25%", "format": "percentage"},
    "video_50": {"label": "Video Played to 50%", "format": "percentage"},
    "video_75": {"label": "Video Played to 75%", "format": "percentage"},
    "video_100": {"label": "Video Played to 100%", "format": "percentage"},
    "cpv": {"label": "CPV", "format": "currency"},
}


def _objective(
    key: str,
    label: str,
    default_metrics: list[str],
    primary: str,
    available_metrics: list[str] | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "primary_metric": primary,
        "metric_keys": list(available_metrics or default_metrics),
        "default_metric_keys": list(default_metrics),
    }


META_AVAILABLE_METRICS = [
    "result",
    "reach",
    "impressions",
    "post_engagements",
    "interactions",
    "post_shares",
    "post_saves",
    "post_reactions",
    "post_comments",
    "link_clicks",
    "frequency",
    "ctr",
    "engagement_rate",
    "result_rate",
    "cost_per_result",
    "spend",
    "thruplay",
]


OBJECTIVE_CATALOG = {
    "meta": {
        "label": "Meta Ads",
        "available": True,
        "platform_scopes": ["meta", "instagram", "facebook"],
        "objectives": [
            _objective("reach", "Reach", ["reach", "impressions", "post_engagements", "link_clicks", "frequency", "ctr", "engagement_rate", "cost_per_result", "spend"], "reach", META_AVAILABLE_METRICS),
            _objective("engagement", "Engagement", ["reach", "impressions", "post_engagements", "interactions", "post_shares", "post_saves", "post_reactions", "post_comments", "link_clicks", "frequency", "ctr", "engagement_rate", "cost_per_result", "spend"], "post_engagements", META_AVAILABLE_METRICS),
            _objective("views", "Views", ["reach", "impressions", "post_engagements", "thruplay", "link_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "result", META_AVAILABLE_METRICS),
            _objective("link_clicks", "Link Clicks", ["reach", "impressions", "post_engagements", "link_clicks", "frequency", "ctr", "engagement_rate", "cost_per_result", "spend"], "link_clicks", META_AVAILABLE_METRICS),
            _objective("leads", "Leads", ["result", "reach", "impressions", "post_engagements", "link_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "leads", META_AVAILABLE_METRICS),
        ],
    },
    "google_sem": {
        "label": "Google SEM",
        "available": False,
        "platform_scopes": ["google_sem"],
        "objectives": [_objective("performance", "Performance", ["impressions", "clicks", "ctr", "cpm", "cpc", "spend"], "clicks")],
    },
    "google_gdn": {
        "label": "Google Display Network",
        "available": False,
        "platform_scopes": ["google_gdn"],
        "objectives": [_objective("performance", "Performance", ["impressions", "clicks", "ctr", "cpm", "cpc", "spend"], "clicks")],
    },
    "youtube": {
        "label": "YouTube Ads",
        "available": False,
        "platform_scopes": ["youtube"],
        "objectives": [_objective("video_views", "Video Views", ["impressions", "clicks", "trueview_views", "viewable_rate", "video_25", "video_50", "video_75", "video_100", "cpm", "cpv", "spend"], "trueview_views")],
    },
    "tiktok": {
        "label": "TikTok Ads",
        "available": False,
        "platform_scopes": ["tiktok"],
        "objectives": [
            _objective("reach", "Reach", ["reach", "impressions", "video_views", "video_views_2s", "video_views_6s", "paid_follows", "destination_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "reach"),
            _objective("views", "Views", ["reach", "impressions", "video_views", "video_views_2s", "video_views_6s", "paid_follows", "destination_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "video_views"),
            _objective("traffic", "Traffic", ["reach", "impressions", "video_views", "video_views_2s", "video_views_6s", "paid_follows", "destination_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "destination_clicks"),
            _objective("community_interaction", "Community Interaction", ["reach", "impressions", "video_views", "video_views_2s", "video_views_6s", "paid_follows", "destination_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "paid_follows"),
            _objective("leads", "Leads", ["result", "reach", "impressions", "video_views", "video_views_2s", "video_views_6s", "destination_clicks", "frequency", "ctr", "result_rate", "cost_per_result", "spend"], "leads"),
        ],
    },
}


def objective_catalog() -> dict:
    catalog = deepcopy(OBJECTIVE_CATALOG)
    for scope in catalog.values():
        for objective in scope["objectives"]:
            objective["metrics"] = [
                {"key": key, **METRICS[key]}
                for key in objective["metric_keys"]
            ]
    return {"scopes": catalog, "metrics": deepcopy(METRICS)}


def objective_definition(scope: str, objective_key: str) -> dict:
    scope_definition = OBJECTIVE_CATALOG.get(str(scope or "").lower())
    if not scope_definition:
        raise ValueError("Unsupported Ads metric configuration scope.")
    for objective in scope_definition["objectives"]:
        if objective["key"] == str(objective_key or "").lower():
            return objective
    raise ValueError(f"Unsupported objective for {scope_definition['label']}.")


def normalize_metric_keys(scope: str, objective_key: str, metric_keys) -> list[str]:
    definition = objective_definition(scope, objective_key)
    if not isinstance(metric_keys, list):
        raise ValueError("metric_keys must be an ordered list.")
    allowed = set(definition["metric_keys"])
    normalized = []
    for raw_key in metric_keys:
        key = str(raw_key or "").strip().lower()
        if key not in allowed:
            raise ValueError(f"Unsupported metric for {definition['label']}: {key or '(empty)' }.")
        if key not in normalized:
            normalized.append(key)
    return normalized


def suggest_meta_objective(campaign_objective=None, optimization_goals=None, result_types=None) -> dict:
    campaign = str(campaign_objective or "").upper()
    signals = " ".join(
        str(item or "").upper()
        for item in [campaign, *(optimization_goals or []), *(result_types or [])]
    )
    if "LEAD" in signals:
        suggestion, confidence = "leads", "high"
    elif any(value in signals for value in ("THRUPLAY", "VIDEO_VIEW", "VIDEO VIEWS")):
        suggestion, confidence = "views", "high"
    elif any(value in signals for value in ("LINK_CLICK", "LANDING_PAGE_VIEW", "OUTCOME_TRAFFIC")):
        suggestion, confidence = "link_clicks", "high"
    elif any(value in signals for value in ("POST_ENGAGEMENT", "POST_INTERACTION")):
        suggestion, confidence = "engagement", "high"
    elif "REACH" in signals:
        suggestion, confidence = "reach", "high"
    elif "OUTCOME_AWARENESS" in campaign:
        suggestion, confidence = "reach", "medium"
    elif "OUTCOME_ENGAGEMENT" in campaign:
        suggestion, confidence = "engagement", "medium"
    else:
        suggestion, confidence = "reach", "low"
    return {"objective": suggestion, "confidence": confidence}


def result_metric_for_objective(objective_key: str) -> str:
    return {
        "reach": "reach",
        "engagement": "post_engagements",
        "views": "video_views",
        "link_clicks": "link_clicks",
        "leads": "leads",
    }.get(str(objective_key or "").lower(), "result")
