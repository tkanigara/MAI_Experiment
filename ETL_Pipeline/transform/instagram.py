import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from ai_insight_pipeline import REQUIRED_FIELDS
from analytics_pipeline import calculate_instagram_kpi, json_safe


def read_csv_dicts(path):
    if not path:
        return []
    csv_path = Path(path)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def number(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def first_value(row, keys, default=""):
    for key in keys:
        value = row.get(key, "")
        if value not in ("", None):
            return value
    return default


def normalize_content_type(row):
    product_type = str(row.get("media_product_type", "")).strip().upper()
    media_type = str(row.get("media_type", "")).strip().upper()
    if product_type:
        return product_type
    if media_type == "VIDEO":
        return "REELS"
    return media_type or "UNKNOWN"


def build_post(row):
    likes = number(first_value(row, ["insight_likes", "like_count"], 0))
    comments = number(first_value(row, ["insight_comments", "comments_count"], 0))
    shares = number(row.get("insight_shares", 0))
    saved = number(first_value(row, ["insight_saved", "insight_saves"], 0))
    interactions = number(first_value(row, ["insight_total_interactions", "insight_engagement"], 0))
    if not interactions:
        interactions = likes + comments + shares + saved
    reach = number(row.get("insight_reach", 0))
    views = number(first_value(row, ["insight_views", "insight_impressions", "insight_video_views"], 0))
    engagement_rate = interactions / reach * 100 if reach else 0.0

    return {
        "media_id": row.get("id", ""),
        "posted_at": row.get("timestamp", ""),
        "date": str(row.get("timestamp", ""))[:10] if row.get("timestamp") else "",
        "caption": row.get("caption", ""),
        "content_type": normalize_content_type(row),
        "media_type": row.get("media_type", ""),
        "media_product_type": row.get("media_product_type", ""),
        "permalink": row.get("permalink", ""),
        "media_url": row.get("media_url", ""),
        "thumbnail_url": row.get("thumbnail_url", ""),
        "reach": reach,
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saved": saved,
        "interactions": interactions,
        "engagement_rate": engagement_rate,
        "metric_errors": row.get("metric_errors", ""),
        "raw": row,
    }


def rank_posts(posts):
    ranked = sorted(posts, key=lambda post: (post["interactions"], post["reach"]), reverse=True)
    for index, post in enumerate(ranked, start=1):
        post["rank_by_interactions"] = index
        post["is_top_3_content"] = index <= 3
    return ranked


def transform_instagram_raw(
    media_csv,
    account_csv=None,
    client_id="",
    client_name="",
    run_id="",
    frequency="",
    ai_insights=None,
):
    """Transform raw Instagram CSV files into one processed JSON-friendly object."""
    media_csv = Path(media_csv)
    account_csv = Path(account_csv) if account_csv else None
    kpi_summary = calculate_instagram_kpi(media_csv, account_csv)
    account = kpi_summary.get("account", {})
    resolved_client_name = (
        client_name
        or os.getenv("REPORT_CLIENT_NAME", "").strip()
        or account.get("name")
        or account.get("username")
        or client_id
    )

    posts = [build_post(row) for row in read_csv_dicts(media_csv)]
    posts = rank_posts(posts)

    processed = {
        "run_id": run_id,
        "client_id": client_id,
        "client_name": resolved_client_name,
        "platform": "instagram",
        "frequency": frequency,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            "media_csv": str(media_csv),
            "account_csv": str(account_csv) if account_csv else "",
        },
        "account": account,
        "summary": {
            "total_posts": kpi_summary.get("total_posts", 0),
            "total_reach": kpi_summary.get("total_reach", 0),
            "total_views": kpi_summary.get("total_views", 0),
            "total_likes": kpi_summary.get("total_likes", 0),
            "total_comments": kpi_summary.get("total_comments", 0),
            "total_shares": kpi_summary.get("total_shares", 0),
            "total_saved": kpi_summary.get("total_saved", 0),
            "total_interactions": kpi_summary.get("total_interactions", 0),
            "avg_engagement_rate": kpi_summary.get("avg_engagement_rate", 0),
            "best_content_type": kpi_summary.get("best_content_type", ""),
        },
        "content_type_stats": kpi_summary.get("content_type_stats", {}),
        "feed_stats": kpi_summary.get("feed_stats", {}),
        "reels_stats": kpi_summary.get("reels_stats", {}),
        "monthly_stats": kpi_summary.get("monthly_stats", []),
        "posts": posts,
        "ai_insights": {
            field: (ai_insights or {}).get(field, "")
            for field in REQUIRED_FIELDS
        },
        "warning": (ai_insights or {}).get("warning", ""),
        "kpi_summary": kpi_summary,
    }
    return json_safe(processed)
