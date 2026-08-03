from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text

try:
    from dashboard.db import create_db_engine
    from dashboard.repositories.report_data_lock import (
        lock_client_report_periods,
        lock_client_report_year,
        lock_existing_report_period,
        lock_report_period,
    )
except ModuleNotFoundError:
    from db import create_db_engine
    from repositories.report_data_lock import (
        lock_client_report_periods,
        lock_client_report_year,
        lock_existing_report_period,
        lock_report_period,
    )

PLATFORM_TABLES = {
    "instagram": "instagram_reports",
    "facebook": "facebook_reports",
    "tiktok": "tiktok_reports",
    "youtube": "youtube_reports",
    "linkedin": "linkedin_reports",
    "threads": "threads_reports",
}

PLATFORM_DATA_FIELDS = {
    "instagram": [
        ("total_followers", "Total followers"),
        ("follower_growth", "Follower growth"),
        ("follower_growth_rate", "Follower growth rate"),
        ("follows", "Follows"),
        ("unfollows", "Unfollows"),
        ("reach", "Reach"),
        ("impressions", "Impressions"),
        ("total_engagement", "Total engagement"),
        ("engagement_rate", "Engagement rate"),
        ("likes", "Likes"),
        ("comments", "Comments"),
        ("shares", "Shares"),
        ("saves", "Saves"),
        ("reposts", "Reposts"),
        ("total_posts", "Total posts"),
        ("reels_posts", "Reels posts"),
        ("carousel_posts", "Carousel posts"),
        ("single_posts", "Single posts"),
        ("story_posts", "Story posts"),
        ("demographics", "Audience demographics"),
    ],
    "facebook": [
        ("total_followers", "Total followers"),
        ("follower_growth", "Follower growth"),
        ("follower_growth_rate", "Follower growth rate"),
        ("follows", "Follows"),
        ("unfollows", "Unfollows"),
        ("reach", "Reach"),
        ("impressions", "Impressions"),
        ("total_engagement", "Total engagement"),
        ("engagement_rate", "Engagement rate"),
        ("likes", "Likes"),
        ("comments", "Comments"),
        ("shares", "Shares"),
        ("reactions", "Reactions"),
        ("total_posts", "Total posts"),
        ("reels_posts", "Reels posts"),
        ("carousel_posts", "Carousel posts"),
        ("single_posts", "Single posts"),
        ("story_posts", "Story posts"),
        ("demographics", "Audience demographics"),
    ],
    "tiktok": [
        ("total_followers", "Total followers"),
        ("follower_growth", "Follower growth"),
        ("follower_growth_rate", "Follower growth rate"),
        ("follows", "Follows"),
        ("unfollows", "Unfollows"),
        ("total_views", "Total views"),
        ("reach", "Reach"),
        ("total_engagement", "Total engagement"),
        ("engagement_rate", "Engagement rate"),
        ("likes", "Likes"),
        ("comments", "Comments"),
        ("shares", "Shares"),
        ("saves", "Saves"),
        ("total_posts", "Total posts"),
        ("video_posts", "Video posts"),
        ("demographics", "Audience demographics"),
    ],
    "youtube": [
        ("total_subscribers", "Total subscribers"),
        ("subscriber_growth", "Subscriber growth"),
        ("subscriber_growth_rate", "Subscriber growth rate"),
        ("subscribers_lost", "Subscribers lost"),
        ("total_views", "Total views"),
        ("reach", "Reach"),
        ("total_engagement", "Total engagement"),
        ("engagement_rate", "Engagement rate"),
        ("likes", "Likes"),
        ("comments", "Comments"),
        ("shares", "Shares"),
        ("total_posts", "Total posts"),
        ("video_posts", "Video posts"),
        ("shorts_posts", "Shorts posts"),
        ("long_form_posts", "Long-form posts"),
        ("live_posts", "Live posts"),
        ("demographics", "Audience demographics"),
    ],
    "linkedin": [
        ("total_followers", "Total followers"),
        ("follower_growth", "Follower growth"),
        ("follower_growth_rate", "Follower growth rate"),
        ("follows", "Follows"),
        ("unfollows", "Unfollows"),
        ("impressions", "Impressions"),
        ("reach", "Reach"),
        ("total_engagement", "Total engagement"),
        ("engagement_rate", "Engagement rate"),
        ("likes", "Likes"),
        ("comments", "Comments"),
        ("shares", "Shares"),
        ("reposts", "Reposts"),
        ("total_posts", "Total posts"),
        ("photo_posts", "Photo posts"),
        ("video_posts", "Video posts"),
        ("demographics", "Audience demographics"),
    ],
    "threads": [
        ("total_followers", "Total followers"),
        ("follower_growth", "Follower growth"),
        ("follower_growth_rate", "Follower growth rate"),
        ("follows", "Follows"),
        ("unfollows", "Unfollows"),
        ("total_views", "Total views"),
        ("reach", "Reach"),
        ("total_engagement", "Total engagement"),
        ("engagement_rate", "Engagement rate"),
        ("likes", "Likes"),
        ("comments", "Comments"),
        ("shares", "Shares"),
        ("reposts", "Reposts"),
        ("total_posts", "Total posts"),
        ("text_posts", "Text posts"),
        ("photo_posts", "Photo posts"),
        ("video_posts", "Video posts"),
        ("demographics", "Audience demographics"),
    ],
}
PLATFORM_KPI_METRICS = {
    "instagram": {"followers", "engagement", "reach"},
    "facebook": {"followers", "engagement", "reach"},
    "tiktok": {"followers", "likes", "views"},
    "youtube": {"subscribers", "engagement", "views"},
    "linkedin": {"followers", "engagement", "impressions"},
    "threads": {"followers", "engagement", "views"},
}
CUMULATIVE_KPI_FIELDS = {
    "instagram": {"engagement": "total_engagement", "reach": "reach"},
    "facebook": {"engagement": "total_engagement", "reach": "reach"},
    "tiktok": {"likes": "likes", "views": "total_views"},
    "youtube": {"engagement": "total_engagement", "views": "total_views"},
    "linkedin": {"engagement": "total_engagement", "impressions": "impressions"},
    "threads": {"engagement": "total_engagement", "views": "total_views"},
}
CSV_IMPORT_SLOTS = {
    "account": {
        "label": "Account Data",
        "platform": None,
        "required_columns": [
            "Profile",
            "Social network",
            "Follower",
            "Number of posts",
            "Number of Likes",
            "Number of comments",
            "Profile-ID",
            "Link",
            "Image Link",
        ],
        "important_columns": ["Follower", "Number of posts", "Engagement"],
    },
    "competitor": {
        "label": "Competitor Data",
        "platform": None,
        "required_columns": [
            "Profile",
            "Social network",
            "Follower",
            "Number of posts",
            "Number of Likes",
            "Number of comments",
            "Profile-ID",
            "Link",
            "Image Link",
        ],
        "important_columns": ["Follower", "Number of posts", "Engagement"],
    },
    "competitor_content": {
        "label": "Competitor Content",
        "platform": None,
        "optional": True,
        "required_columns": ["Date", "Profile", "Message", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Engagement", "Number of Likes"],
    },
    "all_content": {
        "label": "All Platform Content",
        "platform": None,
        "required_columns": [
            "Date",
            "Profile",
            "Message",
            "Number of Likes",
            "Number of comments",
            "Post-ID",
            "Link",
            "Image Link",
        ],
        "important_columns": [
            "Reactions, Comments & Shares",
            "Reach per post",
            "Impressions/views per post",
            "Engagement",
        ],
    },
    "ig_post": {
        "label": "Instagram Posts",
        "platform": "instagram",
        "optional": True,
        "legacy": True,
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Reach per post", "Engagement"],
    },
    "ig_story": {
        "label": "Instagram Stories",
        "platform": "instagram",
        "required_columns": ["Date", "Profile", "Story reach", "Story views", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Story reach", "Story views", "Story replies", "Story shares"],
    },
    "fb_post": {
        "label": "Facebook Posts",
        "platform": "facebook",
        "optional": True,
        "legacy": True,
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Reach per post", "Engagement"],
    },
    "tt_post": {
        "label": "TikTok Posts",
        "platform": "tiktok",
        "optional": True,
        "legacy": True,
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Impressions/views per post", "Engagement"],
    },
    "yt_post": {
        "label": "YouTube Posts",
        "platform": "youtube",
        "optional": True,
        "legacy": True,
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Impressions/views per post", "Engagement"],
    },
}
SOCIAL_NETWORK_PLATFORMS = {
    "INSTAGRAM": "instagram",
    "FACEBOOK": "facebook",
    "TIKTOK": "tiktok",
    "YOUTUBE": "youtube",
    "LINKEDIN": "linkedin",
    "LINKEDIN COMPANY": "linkedin",
    "THREADS": "threads",
}
PLATFORM_CONTENT_SLOTS = {
    "instagram": ("all_content", "ig_post", "ig_story"),
    "facebook": ("all_content", "fb_post"),
    "tiktok": ("all_content", "tt_post"),
    "youtube": ("all_content", "yt_post"),
    "linkedin": ("all_content",),
    "threads": ("all_content",),
}
PRIMARY_CSV_IMPORT_SLOTS = (
    "account",
    "competitor",
    "competitor_content",
    "all_content",
    "ig_story",
)
LEGACY_CONTENT_SLOTS = ("ig_post", "fb_post", "tt_post", "yt_post")


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    return value


def row_dict(row):
    return json_safe(dict(row)) if row else None


def clean_header(name: str | None) -> str:
    return (name or "").strip().lstrip("\ufeff")


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    text_value = text_value.replace("%", "").replace(",", ".")
    try:
        return float(text_value)
    except ValueError:
        return None


def normalized_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def client_code_base(client_name: str) -> str:
    normalized_name = unicodedata.normalize("NFKD", client_name)
    ascii_name = normalized_name.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "client"


def available_client_code(base_code: str, existing_codes) -> str:
    used_codes = {str(code) for code in existing_codes}
    if base_code not in used_codes:
        return base_code

    suffix = 2
    while f"{base_code}-{suffix}" in used_codes:
        suffix += 1
    return f"{base_code}-{suffix}"


def row_value(row: dict, *keys: str):
    if not row:
        return None
    by_normalized = {normalized_key(key): value for key, value in row.items()}
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
        value = by_normalized.get(normalized_key(key))
        if value not in (None, ""):
            return value
    return None


def number_from(row: dict, *keys: str):
    return parse_number(row_value(row, *keys))


def percent_from(row: dict, *keys: str):
    value = row_value(row, *keys)
    number = parse_number(value)
    if number is None:
        return None
    if "%" in str(value):
        return round(number, 2)
    return round(number * 100, 2) if abs(number) <= 1 else round(number, 2)


def numeric(row: dict, key: str, default=0):
    value = parse_number(row.get(key))
    return default if value is None else value


def sum_optional(*values):
    parsed = [value for value in values if value is not None]
    if not parsed:
        return None
    return sum(parsed)


def engagement_percent(value):
    number = parse_number(value)
    if number is None:
        return None
    return round(number * 100, 2) if abs(number) <= 1 else round(number, 2)


def parse_post_date(value):
    if not value:
        return None
    normalized = str(value).replace("\u202f", " ").strip()
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in (
        "%d/%m/%Y, %H:%M",
        "%d/%m/%Y %H:%M",
        "%m/%d/%y, %I:%M %p",
        "%m/%d/%Y, %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def month_range_from_slug(slug: str):
    try:
        month_name, year_text = slug.rsplit("-", 1)
        month_number = list(calendar.month_name).index(month_name.capitalize())
        year = int(year_text)
    except (ValueError, IndexError):
        raise ValueError("Invalid report month")
    last_day = calendar.monthrange(year, month_number)[1]
    label = f"{calendar.month_name[month_number]} {year}"
    return date(year, month_number, 1), date(year, month_number, last_day), label


def month_slug_from_date(value):
    return f"{calendar.month_name[value.month].lower()}-{value.year}"


def parse_csv_upload(file_item):
    raw = file_item.file.read()
    text_value = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text_value), delimiter=";")
    headers = [clean_header(header) for header in (reader.fieldnames or []) if clean_header(header)]
    rows = []
    for row in reader:
        rows.append({clean_header(key): (value or "").strip() for key, value in row.items() if clean_header(key)})
    return headers, rows


def validate_csv_rows(slot: str, headers: list[str], rows: list[dict]):
    spec = CSV_IMPORT_SLOTS[slot]
    warnings = []
    missing_columns = [column for column in spec["required_columns"] if column not in headers]
    if missing_columns:
        warnings.append(f"Missing columns: {', '.join(missing_columns)}")
    if not rows:
        warnings.append("File has no data rows.")
        return warnings
    for column in spec["important_columns"]:
        if column in headers:
            empty_count = sum(1 for row in rows if not str(row.get(column, "")).strip())
            if empty_count:
                warnings.append(f"{column} empty in {empty_count}/{len(rows)} rows.")
        else:
            warnings.append(f"{column} is unavailable, related metrics may be incomplete.")
    return warnings


def platform_from_row(row: dict):
    return SOCIAL_NETWORK_PLATFORMS.get(str(row.get("Social network", "")).strip().upper())


def platform_from_content_row(
    row: dict,
    profile_platforms: dict[str, str] | None = None,
):
    platform = platform_from_row(row)
    if platform:
        return platform
    link = str(row.get("Link", "")).lower()
    if "instagram." in link:
        return "instagram"
    if "facebook." in link or "fb.watch" in link:
        return "facebook"
    if "tiktok." in link:
        return "tiktok"
    if "youtube." in link or "youtu.be" in link:
        return "youtube"
    if "linkedin." in link or "lnkd.in" in link:
        return "linkedin"
    if "threads.net" in link:
        return "threads"
    profile_id = str(row.get("Profile-ID", "") or "").strip()
    if profile_id and profile_platforms:
        return profile_platforms.get(profile_id)
    return None


def default_content_type(platform: str) -> str:
    return {
        "tiktok": "video",
        "youtube": "video",
        "linkedin": "photo",
        "threads": "text",
    }.get(platform, "post")


def content_type_from_row(row: dict, platform: str, fallback: str) -> str:
    raw_type = str(
        row.get("Content type")
        or row.get("Post type")
        or row.get("Media type")
        or row.get("Type")
        or ""
    ).strip().lower()
    if fallback == "story" or number_from(row, "Number of Stories"):
        detected = "story"
    elif number_from(row, "Number of Carousels/Albums") or any(
        token in raw_type for token in ("carousel", "album", "document")
    ):
        detected = "carousel"
    elif number_from(row, "Number of Reels/Shorts"):
        detected = "short" if platform == "youtube" else "reel"
    elif number_from(row, "Number of Video Posts", "Number of Videos") or any(
        token in raw_type for token in ("video", "reel", "short", "live")
    ):
        detected = "video"
    elif number_from(row, "Number of Image Posts", "Number of Photo Posts") or any(
        token in raw_type for token in ("image", "photo", "picture")
    ):
        detected = "image"
    elif raw_type in {"text", "status", "link"}:
        detected = "text"
    else:
        detected = fallback

    if platform == "linkedin":
        return "video" if detected in {"video", "reel", "short", "live"} else "photo"
    if platform == "threads":
        if detected in {"video", "reel", "short", "live"}:
            return "video"
        if detected in {"image", "photo", "carousel"}:
            return "photo"
        return "text"
    return detected


def post_json(row: dict, content_type: str, platform: str):
    total_engagement = parse_number(row.get("Reactions, Comments & Shares"))
    likes = float(number_from(row, "Number of Likes") or 0)
    comments = float(
        number_from(row, "Number of comments", "Story replies") or 0
    )
    shares = float(
        number_from(
            row,
            "Number of Shares",
            "Shares",
            "Story shares",
        )
        or 0
    )
    saves = float(number_from(row, "Number of Saves", "Saves") or 0)
    reposts = float(number_from(row, "Number of Reposts", "Reposts") or 0)
    reactions = float(
        number_from(row, "Number of Reactions", "Reactions") or 0
    )
    if total_engagement is None:
        total_engagement = (
            likes
            + comments
            + shares
            + saves
            + reposts
            + reactions
        )
    post_id = str(row.get("Post-ID") or "").strip()
    if not post_id:
        identity_source = str(row.get("Link") or "").strip()
        identity_kind = "url"
        if not identity_source:
            identity_source = "|".join(
                (
                    str(row.get("Message") or "").strip(),
                    str(row.get("Date") or "").strip(),
                )
            )
            identity_kind = "content"
        digest = hashlib.sha256(identity_source.encode("utf-8")).hexdigest()[:24]
        post_id = f"{identity_kind}:{digest}"
    return {
        "post_id": post_id,
        "published_at": json_safe(parse_post_date(row.get("Date"))),
        "source_published_at": row.get("Date"),
        "caption": row.get("Message") or "-",
        "permalink": row.get("Link"),
        "image_url": row.get("Image Link"),
        "content_type": content_type_from_row(row, platform, content_type),
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "reposts": reposts,
        "reactions": reactions,
        "views": parse_number(row.get("Impressions/views per post") or row.get("Story views")),
        "reach": parse_number(row.get("Reach per post") or row.get("Story reach")),
        "profile_visits": parse_number(
            row.get("Profile visits based on the story")
        ),
        "total_engagement": total_engagement,
        "engagement_rate": engagement_percent(row.get("Engagement") or row.get("Post interaction rate")),
    }


def content_identity(post: dict) -> tuple:
    if post.get("post_id"):
        return ("post_id", str(post["post_id"]))
    if post.get("permalink"):
        return ("permalink", str(post["permalink"]))
    return (
        "content",
        str(post.get("caption") or ""),
        str(post.get("published_at") or ""),
    )


def deduplicate_content_rows(
    rows: list[dict],
    platform: str,
    fallback_content_type: str,
) -> tuple[list[dict], int]:
    unique_rows = []
    seen = set()
    duplicates = 0
    for row in rows:
        if str(row.get("Post-ID", "") or "").strip().upper() == "SUMME":
            continue
        identity = content_identity(
            post_json(row, fallback_content_type, platform)
        )
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        unique_rows.append(row)
    return unique_rows, duplicates


def split_combined_content_rows(
    rows: list[dict],
    profile_platforms: dict[str, str] | None = None,
) -> tuple[dict[str, list[dict]], dict]:
    split_rows = {platform: [] for platform in PLATFORM_TABLES}
    unknown_rows = []
    summary_rows = 0
    for row_number, row in enumerate(rows, start=2):
        if str(row.get("Post-ID", "") or "").strip().upper() == "SUMME":
            summary_rows += 1
            continue
        platform = platform_from_content_row(row, profile_platforms)
        if platform not in split_rows:
            unknown_rows.append(
                {
                    "row": row_number,
                    "profile": row.get("Profile"),
                    "profile_id": row.get("Profile-ID"),
                    "post_id": row.get("Post-ID"),
                    "link": row.get("Link"),
                }
            )
            continue
        split_rows[platform].append(row)

    detected = {
        platform: len(platform_rows)
        for platform, platform_rows in split_rows.items()
    }
    duplicates = {}
    for platform, platform_rows in split_rows.items():
        fallback = default_content_type(platform)
        split_rows[platform], duplicates[platform] = deduplicate_content_rows(
            platform_rows,
            platform,
            fallback,
        )

    return split_rows, {
        "detected": detected,
        "summary_rows_skipped": summary_rows,
        "unknown_rows": unknown_rows,
        "unknown_count": len(unknown_rows),
        "duplicates_skipped": duplicates,
    }


def summarize_posts(rows: list[dict], content_type: str, platform: str):
    summary_rows = [row for row in rows if str(row.get("Post-ID", "")).strip().upper() == "SUMME"]
    content_rows = [row for row in rows if str(row.get("Post-ID", "")).strip().upper() != "SUMME"]
    content_rows, _duplicates = deduplicate_content_rows(
        content_rows,
        platform,
        content_type,
    )
    posts = [post_json(row, content_type, platform) for row in content_rows]
    summary = summarize_post_objects(posts, content_type)
    if summary_rows:
        summary_post = post_json(summary_rows[0], content_type, platform)
        summary["totals"].update(
            {
                "likes": summary_post.get("likes") or 0,
                "comments": summary_post.get("comments") or 0,
                "shares": summary_post.get("shares") or 0,
                "saves": summary_post.get("saves") or 0,
                "reposts": summary_post.get("reposts") or 0,
                "reactions": summary_post.get("reactions") or 0,
                "reach": summary_post.get("reach") or 0,
                "views": summary_post.get("views") or 0,
                "engagement": summary_post.get("total_engagement") or 0,
            }
        )
    return summary


def summarize_post_objects(posts: list[dict], fallback_content_type: str = "post"):
    posts = [dict(post) for post in posts]

    def total_value(item: dict, key: str) -> float:
        value = parse_number(item.get(key))
        return float(value) if value is not None else 0.0

    content_type_counts = {}
    for post in posts:
        post_type = post.get("content_type") or fallback_content_type
        content_type_counts[post_type] = content_type_counts.get(post_type, 0) + 1
    posts.sort(key=lambda item: item.get("total_engagement") or 0, reverse=True)
    top_posts = posts[:3]
    top_identities = {content_identity(post) for post in top_posts}
    low_posts = [
        post
        for post in sorted(posts, key=lambda item: item.get("total_engagement") or 0)
        if content_identity(post) not in top_identities
    ][:3]
    totals = {
        "likes": sum(total_value(item, "likes") for item in posts),
        "comments": sum(total_value(item, "comments") for item in posts),
        "shares": sum(total_value(item, "shares") for item in posts),
        "saves": sum(total_value(item, "saves") for item in posts),
        "reposts": sum(total_value(item, "reposts") for item in posts),
        "reactions": sum(total_value(item, "reactions") for item in posts),
        "reach": sum(total_value(item, "reach") for item in posts),
        "views": sum(total_value(item, "views") for item in posts),
        "engagement": sum(
            total_value(item, "total_engagement") for item in posts
        ),
        "count": len(posts),
    }
    return {
        "top_posts": top_posts,
        "low_posts": low_posts,
        "totals": totals,
        "raw_posts": posts,
        "content_type_counts": content_type_counts,
    }


class DashboardRepository:
    def __init__(self):
        self.engine = create_db_engine()

    def clients(self):
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        c.id,
                        c.client_code,
                        c.client_name,
                        c.industry,
                        c.has_instagram,
                        c.has_facebook,
                        c.has_tiktok,
                        c.has_youtube,
                        c.has_linkedin,
                        c.has_threads,
                        COUNT(p.id) FILTER (WHERE p.is_active) AS connected_profiles
                    FROM clients c
                    LEFT JOIN client_social_profiles p ON p.client_id = c.id
                    WHERE c.is_active
                    GROUP BY c.id
                    ORDER BY c.client_name
                    """
                )
            ).mappings()
            return [row_dict(row) for row in rows]

    def create_client(self, payload: dict):
        required = ["client_name"]
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")
        client_name = str(payload["client_name"]).strip()
        base_code = client_code_base(client_name)
        with self.engine.begin() as conn:
            # Allocate readable client codes safely even when two requests for
            # the same client name arrive concurrently.
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:base_code))"),
                {"base_code": base_code},
            )
            existing_codes = conn.execute(
                text(
                    """
                    SELECT client_code
                    FROM clients
                    WHERE client_code = :base_code
                       OR client_code LIKE :code_prefix
                    """
                ),
                {
                    "base_code": base_code,
                    "code_prefix": f"{base_code}-%",
                },
            ).scalars()
            client_code = available_client_code(base_code, existing_codes)
            row = conn.execute(
                text(
                    """
                    INSERT INTO clients (
                        client_code, client_name, industry,
                        has_instagram, has_facebook, has_tiktok, has_youtube,
                        has_linkedin, has_threads
                    )
                    VALUES (
                        :client_code, :client_name, :industry,
                        :has_instagram, :has_facebook, :has_tiktok, :has_youtube,
                        :has_linkedin, :has_threads
                    )
                    RETURNING id, client_code, client_name, industry,
                              has_instagram, has_facebook, has_tiktok, has_youtube,
                              has_linkedin, has_threads,
                              0 AS connected_profiles
                    """
                ),
                {
                    "client_code": client_code,
                    "client_name": client_name,
                    "industry": payload.get("industry") or None,
                    "has_instagram": bool(payload.get("has_instagram")),
                    "has_facebook": bool(payload.get("has_facebook")),
                    "has_tiktok": bool(payload.get("has_tiktok")),
                    "has_youtube": bool(payload.get("has_youtube")),
                    "has_linkedin": bool(payload.get("has_linkedin")),
                    "has_threads": bool(payload.get("has_threads")),
                },
            ).mappings().one()
            return row_dict(row)

    def update_client(self, client_id: str, payload: dict):
        required = ["client_name"]
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")
        with self.engine.begin() as conn:
            lock_client_report_periods(conn, client_id)
            row = conn.execute(
                text(
                    """
                    UPDATE clients
                    SET
                        client_name = :client_name,
                        industry = :industry,
                        has_instagram = :has_instagram,
                        has_facebook = :has_facebook,
                        has_tiktok = :has_tiktok,
                        has_youtube = :has_youtube,
                        has_linkedin = :has_linkedin,
                        has_threads = :has_threads,
                        updated_at = now()
                    WHERE id = :client_id
                    RETURNING id, client_code, client_name, industry,
                              has_instagram, has_facebook, has_tiktok, has_youtube,
                              has_linkedin, has_threads,
                              (
                                  SELECT COUNT(*)
                                  FROM client_social_profiles p
                                  WHERE p.client_id = clients.id AND p.is_active
                              ) AS connected_profiles
                    """
                ),
                {
                    "client_id": client_id,
                    "client_name": str(payload["client_name"]).strip(),
                    "industry": payload.get("industry") or None,
                    "has_instagram": bool(payload.get("has_instagram")),
                    "has_facebook": bool(payload.get("has_facebook")),
                    "has_tiktok": bool(payload.get("has_tiktok")),
                    "has_youtube": bool(payload.get("has_youtube")),
                    "has_linkedin": bool(payload.get("has_linkedin")),
                    "has_threads": bool(payload.get("has_threads")),
                },
            ).mappings().first()
            if not row:
                raise ValueError("Client not found")
            return row_dict(row)

    def delete_client(self, client_id: str):
        with self.engine.begin() as conn:
            client = conn.execute(
                text("SELECT id, client_name FROM clients WHERE id = :client_id"),
                {"client_id": client_id},
            ).mappings().first()
            if not client:
                raise ValueError("Client not found")
            lock_client_report_periods(conn, client_id)
            conn.execute(
                text("DELETE FROM raw_api_responses WHERE client_id = :client_id"),
                {"client_id": client_id},
            )
            conn.execute(
                text("DELETE FROM etl_runs WHERE client_id = :client_id"),
                {"client_id": client_id},
            )
            conn.execute(
                text("DELETE FROM clients WHERE id = :client_id"),
                {"client_id": client_id},
            )
            return {"deleted": True, "client_id": client_id, "client_name": client["client_name"]}

    def delete_report_period(self, client_id: str, period_id: str):
        with self.engine.begin() as conn:
            period = lock_report_period(conn, client_id, period_id)

            conn.execute(
                text(
                    """
                    DELETE FROM raw_api_responses
                    WHERE run_id IN (
                        SELECT id
                        FROM etl_runs
                        WHERE client_id = CAST(:client_id AS UUID)
                          AND report_period_id = CAST(:period_id AS UUID)
                    )
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM etl_runs
                    WHERE client_id = CAST(:client_id AS UUID)
                      AND report_period_id = CAST(:period_id AS UUID)
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM report_periods
                    WHERE id = CAST(:period_id AS UUID)
                      AND client_id = CAST(:client_id AS UUID)
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            )
            label = period["period_label"] or period["period_start"].strftime("%B %Y")
            return {
                "deleted": True,
                "client_id": client_id,
                "period_id": period_id,
                "period_label": label,
            }

    def platforms(self, client_id: str):
        with self.engine.begin() as conn:
            client = conn.execute(
                text(
                    """
                    SELECT id, client_code, client_name, industry,
                           has_instagram, has_facebook, has_tiktok, has_youtube,
                           has_linkedin, has_threads
                    FROM clients
                    WHERE id = :client_id
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            profiles = conn.execute(
                text(
                    """
                    SELECT id, platform, profile_name, profile_url, image_url, source_profile_id
                    FROM client_social_profiles
                    WHERE client_id = :client_id AND is_active
                    ORDER BY platform, profile_name
                    """
                ),
                {"client_id": client_id},
            ).mappings()
            return {
                "client": row_dict(client),
                "profiles": [row_dict(row) for row in profiles],
                "report_months": self.report_months(conn, client_id),
            }

    def report_months(self, conn, client_id: str):
        rows = conn.execute(
            text(
                """
                SELECT
                    rp.id,
                    rp.period_label,
                    rp.period_start,
                    rp.period_end,
                    COUNT(DISTINCT CASE
                        WHEN rar.endpoint IN (
                            'csv_import/ig_post',
                            'csv_import/fb_post',
                            'csv_import/tt_post',
                            'csv_import/yt_post',
                            'csv_import/all_content'
                        ) THEN 'csv_import/all_content'
                        WHEN rar.endpoint IN (
                            'csv_import/account',
                            'csv_import/competitor',
                            'csv_import/competitor_content',
                            'csv_import/ig_story'
                        ) THEN rar.endpoint
                        ELSE NULL
                    END) AS uploaded_files,
                    (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM instagram_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                        ) THEN 1 ELSE 0 END
                    ) + (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM facebook_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                        ) THEN 1 ELSE 0 END
                    ) + (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM tiktok_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                        ) THEN 1 ELSE 0 END
                    ) + (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM youtube_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                        ) THEN 1 ELSE 0 END
                    ) + (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM linkedin_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                        ) THEN 1 ELSE 0 END
                    ) + (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM threads_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                        ) THEN 1 ELSE 0 END
                    ) AS platform_reports,
                    (
                        SELECT MAX(updated_at) FROM (
                            SELECT COALESCE(er.finished_at, er.started_at) AS updated_at
                            FROM etl_runs er
                            WHERE er.report_period_id = rp.id
                              AND er.client_id = rp.client_id
                              AND er.status = 'success'
                            UNION ALL
                            SELECT r.updated_at
                            FROM instagram_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                            UNION ALL
                            SELECT r.updated_at
                            FROM facebook_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                            UNION ALL
                            SELECT r.updated_at
                            FROM tiktok_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                            UNION ALL
                            SELECT r.updated_at
                            FROM youtube_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                            UNION ALL
                            SELECT r.updated_at
                            FROM linkedin_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                            UNION ALL
                            SELECT r.updated_at
                            FROM threads_reports r
                            WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                            UNION ALL
                            SELECT rar.fetched_at AS updated_at
                            FROM raw_api_responses rar
                            JOIN etl_runs er ON er.id = rar.run_id
                            WHERE er.report_period_id = rp.id
                              AND rar.client_id = rp.client_id
                              AND rar.endpoint LIKE 'csv_import/%'
                        ) report_updates
                    ) AS last_updated
                FROM report_periods rp
                LEFT JOIN etl_runs er ON er.report_period_id = rp.id AND er.status = 'success'
                LEFT JOIN raw_api_responses rar ON rar.run_id = er.id
                WHERE rp.client_id = :client_id
                GROUP BY rp.id
                ORDER BY rp.period_start DESC
                """
            ),
            {"client_id": client_id},
        ).mappings()
        months = []
        for row in rows:
            uploaded_files = int(row["uploaded_files"] or 0)
            platform_reports = int(row["platform_reports"] or 0)
            status = (
                f"{uploaded_files} of 5 files uploaded"
                if uploaded_files
                else f"{platform_reports} platform reports"
            )
            months.append(
                {
                    "id": row["id"],
                    "label": row["period_label"] or row["period_start"].strftime("%B %Y"),
                    "slug": month_slug_from_date(row["period_start"]),
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "uploaded_files": uploaded_files,
                    "platform_reports": platform_reports,
                    "last_updated": row["last_updated"],
                    "status": status,
                    "state": "ready" if platform_reports else "partial",
                }
            )
        return json_safe(months)

    def overview(self, client_id: str, platform: str, period_id: str | None = None):
        if platform not in PLATFORM_TABLES:
            raise ValueError("Unsupported platform")
        table = PLATFORM_TABLES[platform]
        with self.engine.begin() as conn:
            report = conn.execute(
                text(
                    f"""
                    SELECT
                        r.*,
                        rp.period_label,
                        rp.period_start,
                        rp.period_end,
                        p.profile_name,
                        p.profile_url,
                        p.image_url
                    FROM {table} r
                    JOIN report_periods rp ON rp.id = r.report_period_id
                    LEFT JOIN client_social_profiles p ON p.id = r.profile_id
                    WHERE r.client_id = :client_id
                      AND (
                          CAST(:period_id AS UUID) IS NULL
                          OR r.report_period_id = CAST(:period_id AS UUID)
                      )
                    ORDER BY rp.period_end DESC
                    LIMIT 1
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
            report_data = row_dict(report)
            period_id = report_data["report_period_id"] if report_data else None
            kpi_results = []
            competitor_profiles = []
            content_missing = []
            if period_id:
                kpi_results = [
                    row_dict(row)
                    for row in conn.execute(
                        text(
                            """
                            SELECT metric_name, actual_month, actual_year, target_month,
                                   target_year, achievement_month, achievement_year, unit
                            FROM kpi_results
                            WHERE client_id = :client_id
                              AND platform = :platform
                              AND report_period_id = :period_id
                            ORDER BY metric_name
                            """
                        ),
                        {
                            "client_id": client_id,
                            "platform": platform,
                            "period_id": period_id,
                        },
                    ).mappings()
                ]
                competitor_profiles = [
                    row_dict(row)
                    for row in conn.execute(
                        text(
                            """
                            SELECT
                                profile_name,
                                total_followers,
                                follower_growth,
                                follower_growth_rate,
                                total_posts,
                                total_engagement,
                                engagement_rate,
                                reach,
                                impressions,
                                profile_url,
                                image_url
                            FROM competitor_profile_reports
                            WHERE client_id = :client_id
                              AND platform = :platform
                              AND report_period_id = :period_id
                            ORDER BY total_engagement DESC NULLS LAST, total_followers DESC NULLS LAST
                            """
                        ),
                        {
                            "client_id": client_id,
                            "platform": platform,
                            "period_id": period_id,
                        },
                    ).mappings()
                ]
                content_missing = self.content_missing_data(conn, client_id, period_id, platform)
            kpi_targets = [
                row_dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT id, metric_name, period_year, period_month, target_month,
                               target_year, unit, notes, updated_at
                        FROM kpi_targets
                        WHERE client_id = :client_id AND platform = :platform
                        ORDER BY period_year DESC, period_month DESC, metric_name
                        """
                    ),
                    {"client_id": client_id, "platform": platform},
                ).mappings()
            ]
        if report_data is not None:
            report_data["competitor_profiles"] = competitor_profiles
        kpi_results = dashboard_kpi_results(platform, report_data, kpi_results, kpi_targets)
        missing_data = missing_platform_data(platform, report_data, content_missing)
        return {
            "platform": platform,
            "report": report_data,
            "metrics": overview_metrics(platform, report_data),
            "missing_data": missing_data,
            "kpi_results": kpi_results,
            "kpi_targets": kpi_targets,
            "competitor_profiles": competitor_profiles,
            "top_posts": (report_data or {}).get("top_posts") or [],
            "low_posts": (report_data or {}).get("low_posts") or [],
        }

    def content_missing_data(self, conn, client_id: str, period_id: str, platform: str):
        rows = conn.execute(
            text(
                """
                WITH posts AS (
                    SELECT *
                    FROM social_content_reports
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                      AND platform = :platform
                      AND performance_bucket = 'all'
                )
                SELECT field, missing_count, total_count
                FROM (
                    SELECT 'published_at' AS field, COUNT(*) FILTER (WHERE published_at IS NULL) AS missing_count, COUNT(*) AS total_count FROM posts
                    UNION ALL SELECT 'caption', COUNT(*) FILTER (
                        WHERE COALESCE(content_type, '') <> 'story'
                          AND (caption IS NULL OR btrim(caption) = '' OR caption = '-')
                    ), COUNT(*) FILTER (WHERE COALESCE(content_type, '') <> 'story') FROM posts
                    UNION ALL SELECT 'permalink', COUNT(*) FILTER (WHERE permalink IS NULL OR btrim(permalink) = ''), COUNT(*) FROM posts
                    UNION ALL SELECT 'image_url', COUNT(*) FILTER (WHERE image_url IS NULL OR btrim(image_url) = ''), COUNT(*) FROM posts
                    UNION ALL SELECT 'content_type', COUNT(*) FILTER (WHERE content_type IS NULL OR btrim(content_type) = ''), COUNT(*) FROM posts
                    UNION ALL SELECT 'likes', COUNT(*) FILTER (WHERE likes IS NULL), COUNT(*) FROM posts
                    UNION ALL SELECT 'comments', COUNT(*) FILTER (WHERE comments IS NULL), COUNT(*) FROM posts
                    UNION ALL SELECT 'shares', COUNT(*) FILTER (WHERE shares IS NULL), COUNT(*) FROM posts
                    UNION ALL SELECT 'views', COUNT(*) FILTER (WHERE views IS NULL), COUNT(*) FROM posts
                    UNION ALL SELECT 'reach', COUNT(*) FILTER (WHERE reach IS NULL), COUNT(*) FROM posts
                    UNION ALL SELECT 'profile_visits', COUNT(*) FILTER (
                        WHERE COALESCE(content_type, '') = 'story'
                          AND profile_visits IS NULL
                    ), COUNT(*) FILTER (
                        WHERE COALESCE(content_type, '') = 'story'
                    ) FROM posts
                    UNION ALL SELECT 'total_engagement', COUNT(*) FILTER (WHERE total_engagement IS NULL), COUNT(*) FROM posts
                    UNION ALL SELECT 'engagement_rate', COUNT(*) FILTER (WHERE engagement_rate IS NULL), COUNT(*) FROM posts
                ) checks
                WHERE total_count > 0 AND missing_count > 0
                ORDER BY field
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
            },
        ).mappings()
        labels = {
            "published_at": "Post publish date",
            "caption": "Post caption",
            "permalink": "Post permalink",
            "image_url": "Post image URL",
            "content_type": "Post content type",
            "likes": "Post likes",
            "comments": "Post comments",
            "shares": "Post shares",
            "views": "Post views",
            "reach": "Post reach",
            "total_engagement": "Post total engagement",
            "engagement_rate": "Post engagement rate",
        }
        return [
            {
                "field": f"posts.{row['field']}",
                "label": labels.get(row["field"], row["field"]),
                "missing_count": row["missing_count"],
                "total_count": row["total_count"],
            }
            for row in rows
        ]

    def upsert_kpi_target(self, payload: dict):
        required = ["client_id", "platform", "metric_name", "period_year", "period_month"]
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")
        platform = payload["platform"]
        metric_name = payload["metric_name"].strip().lower().replace(" ", "_")
        if platform not in PLATFORM_TABLES:
            raise ValueError("Unsupported platform")
        if metric_name not in PLATFORM_KPI_METRICS[platform]:
            allowed = ", ".join(sorted(PLATFORM_KPI_METRICS[platform]))
            raise ValueError(f"Unsupported KPI metric for {platform}. Use: {allowed}")
        period_month = int(payload["period_month"])
        if period_month < 1 or period_month > 12:
            raise ValueError("period_month must be between 1 and 12")
        with self.engine.begin() as conn:
            lock_client_report_year(
                conn,
                payload["client_id"],
                int(payload["period_year"]),
            )
            row = conn.execute(
                text(
                    """
                    INSERT INTO kpi_targets (
                        client_id, platform, metric_name, period_year, period_month,
                        target_month, target_year, unit, notes, created_by
                    )
                    VALUES (
                        :client_id, :platform, :metric_name, :period_year, :period_month,
                        :target_month, :target_year, :unit, :notes, :created_by
                    )
                    ON CONFLICT (client_id, platform, metric_name, period_year, period_month)
                    DO UPDATE SET
                        target_month = COALESCE(EXCLUDED.target_month, kpi_targets.target_month),
                        target_year = COALESCE(EXCLUDED.target_year, kpi_targets.target_year),
                        unit = COALESCE(EXCLUDED.unit, kpi_targets.unit),
                        notes = COALESCE(EXCLUDED.notes, kpi_targets.notes),
                        updated_at = now()
                    RETURNING id, metric_name, period_year, period_month, target_month,
                              target_year, unit, notes, updated_at
                    """
                ),
                {
                    "client_id": payload["client_id"],
                    "platform": platform,
                    "metric_name": metric_name,
                    "period_year": int(payload["period_year"]),
                    "period_month": period_month,
                    "target_month": payload.get("target_month") or None,
                    "target_year": payload.get("target_year") or None,
                    "unit": payload.get("unit") or None,
                    "notes": payload.get("notes") or None,
                    "created_by": payload.get("created_by") or "dashboard",
                },
            ).mappings().one()
            synced = self.sync_kpi_results(conn, payload, row["id"], metric_name)
            synced += self.sync_yearly_kpi_results(
                conn,
                payload["client_id"],
                platform,
                metric_name,
                int(payload["period_year"]),
            )
            result = row_dict(row)
            result["synced_results"] = synced
            return result

    def sync_kpi_results(self, conn, payload: dict, target_id, metric_name: str) -> int:
        result = conn.execute(
            text(
                """
                UPDATE kpi_results kr
                SET
                    kpi_target_id = :target_id,
                    target_month = CAST(:target_month AS NUMERIC),
                    target_year = CAST(:target_year AS NUMERIC),
                    unit = COALESCE(:unit, kr.unit),
                    achievement_month = CASE
                        WHEN CAST(:target_month AS NUMERIC) IS NOT NULL
                         AND CAST(:target_month AS NUMERIC) <> 0
                         AND kr.actual_month IS NOT NULL
                        THEN ROUND((kr.actual_month / CAST(:target_month AS NUMERIC)) * 100, 2)
                        ELSE NULL
                    END,
                    achievement_year = CASE
                        WHEN CAST(:target_year AS NUMERIC) IS NOT NULL
                         AND CAST(:target_year AS NUMERIC) <> 0
                         AND kr.actual_year IS NOT NULL
                        THEN ROUND((kr.actual_year / CAST(:target_year AS NUMERIC)) * 100, 2)
                        ELSE NULL
                    END,
                    updated_at = now()
                FROM report_periods rp
                WHERE kr.report_period_id = rp.id
                  AND kr.client_id = :client_id
                  AND kr.platform = :platform
                  AND kr.metric_name = :metric_name
                  AND EXTRACT(YEAR FROM rp.period_start) = :period_year
                  AND EXTRACT(MONTH FROM rp.period_start) = :period_month
                """
            ),
            {
                "target_id": target_id,
                "client_id": payload["client_id"],
                "platform": payload["platform"],
                "metric_name": metric_name,
                "period_year": int(payload["period_year"]),
                "period_month": int(payload["period_month"]),
                "target_month": payload.get("target_month") or None,
                "target_year": payload.get("target_year") or None,
                "unit": payload.get("unit") or None,
            },
        )
        return result.rowcount

    def sync_yearly_kpi_results(self, conn, client_id, platform, metric_name, period_year):
        period_rows = conn.execute(
            text(
                """
                SELECT kr.report_period_id
                FROM kpi_results kr
                JOIN report_periods rp ON rp.id = kr.report_period_id
                WHERE kr.client_id = :client_id
                  AND kr.platform = :platform
                  AND kr.metric_name = :metric_name
                  AND EXTRACT(YEAR FROM rp.period_start) = :period_year
                """
            ),
            {
                "client_id": client_id,
                "platform": platform,
                "metric_name": metric_name,
                "period_year": period_year,
            },
        ).mappings()
        count = 0
        for row in period_rows:
            target = self.effective_kpi_target(
                conn,
                client_id,
                platform,
                metric_name,
                row["report_period_id"],
            )
            result = conn.execute(
                text(
                    """
                    UPDATE kpi_results
                    SET
                        kpi_target_id = :target_id,
                        target_year = :target_year,
                        unit = COALESCE(:unit, unit),
                        achievement_year = CASE
                            WHEN CAST(:target_year AS NUMERIC) IS NOT NULL
                             AND CAST(:target_year AS NUMERIC) <> 0
                             AND actual_year IS NOT NULL
                            THEN ROUND((actual_year / CAST(:target_year AS NUMERIC)) * 100, 2)
                            ELSE NULL
                        END,
                        updated_at = now()
                    WHERE client_id = :client_id
                      AND platform = :platform
                      AND metric_name = :metric_name
                      AND report_period_id = :period_id
                    """
                ),
                {
                    "target_id": target.get("id"),
                    "target_year": target.get("target_year"),
                    "unit": target.get("unit"),
                    "client_id": client_id,
                    "platform": platform,
                    "metric_name": metric_name,
                    "period_id": row["report_period_id"],
                },
            )
            count += result.rowcount
        return count

    def import_csv_report(self, payload: dict, files: dict):
        client_id = payload.get("client_id")
        month_slug = payload.get("month_slug") or "june-2026"
        if not client_id:
            raise ValueError("Missing client_id")
        has_combined_content = bool(
            files.get("all_content")
            and getattr(files["all_content"], "filename", "")
        )
        uploaded_legacy_slots = [
            slot
            for slot in LEGACY_CONTENT_SLOTS
            if files.get(slot) and getattr(files[slot], "filename", "")
        ]
        if has_combined_content and uploaded_legacy_slots:
            raise ValueError(
                "Upload either All Platform Content or legacy per-platform "
                "content files, not both."
            )
        period_start, period_end, period_label = month_range_from_slug(month_slug)
        file_results = []
        parsed_files = {}
        missing_files = []
        for slot, spec in CSV_IMPORT_SLOTS.items():
            file_item = files.get(slot)
            if spec.get("legacy") and (
                file_item is None or not getattr(file_item, "filename", "")
            ):
                continue
            if file_item is None or not getattr(file_item, "filename", ""):
                if slot in PRIMARY_CSV_IMPORT_SLOTS and not spec.get("optional"):
                    missing_files.append(spec["label"])
                file_results.append(
                    {
                        "slot": slot,
                        "label": spec["label"],
                        "filename": None,
                        "rows": 0,
                        "warnings": [] if spec.get("optional") else ["File was not uploaded."],
                    }
                )
                continue
            headers, rows = parse_csv_upload(file_item)
            warnings = validate_csv_rows(slot, headers, rows)
            parsed_files[slot] = {"filename": file_item.filename, "headers": headers, "rows": rows, "warnings": warnings}
            file_results.append(
                {
                    "slot": slot,
                    "label": spec["label"],
                    "filename": file_item.filename,
                    "rows": len(rows),
                    "columns": headers,
                    "warnings": warnings,
                    "preview": rows[:3],
                }
            )

        with self.engine.begin() as conn:
            lock_existing_report_period(
                conn,
                client_id,
                period_start,
                period_end,
            )
            period_id = self.ensure_report_period(conn, client_id, period_start, period_end, period_label)
            run_id = self.create_import_run(conn, client_id, period_id, parsed_files, missing_files)
            profile_ids = self.upsert_account_profiles(conn, client_id, parsed_files.get("account", {}).get("rows", []))
            profile_platforms = self.content_profile_platforms(conn, client_id)
            self.store_raw_csv_rows(conn, run_id, client_id, profile_ids, parsed_files)
            combined_breakdown = {
                "detected": {platform: 0 for platform in PLATFORM_TABLES},
                "summary_rows_skipped": 0,
                "unknown_rows": [],
                "unknown_count": 0,
                "duplicates_skipped": {
                    platform: 0 for platform in PLATFORM_TABLES
                },
            }
            combined_rows = {platform: [] for platform in PLATFORM_TABLES}
            if "all_content" in parsed_files:
                combined_rows, combined_breakdown = split_combined_content_rows(
                    parsed_files["all_content"]["rows"],
                    profile_platforms,
                )
                all_content_warnings = parsed_files["all_content"]["warnings"]
                if combined_breakdown["summary_rows_skipped"]:
                    all_content_warnings.append(
                        f"{combined_breakdown['summary_rows_skipped']} summary "
                        "row(s) skipped; platform totals were recalculated."
                    )
                if combined_breakdown["unknown_count"]:
                    all_content_warnings.append(
                        f"{combined_breakdown['unknown_count']} row(s) skipped "
                        "because their platform could not be identified."
                    )
                for result in file_results:
                    if result["slot"] == "all_content":
                        result["warnings"] = list(all_content_warnings)
                        result["platform_breakdown"] = combined_breakdown
                        break

            instagram_combined_posts = []
            instagram_combined_stories = []
            for row in combined_rows["instagram"]:
                content_type = content_type_from_row(
                    row,
                    "instagram",
                    "post",
                )
                if content_type == "story":
                    instagram_combined_stories.append(row)
                else:
                    instagram_combined_posts.append(row)

            instagram_post_rows = (
                instagram_combined_posts
                if "all_content" in parsed_files
                else parsed_files.get("ig_post", {}).get("rows", [])
            )
            instagram_story_rows = [
                *instagram_combined_stories,
                *parsed_files.get("ig_story", {}).get("rows", []),
            ]
            instagram_story_rows, story_duplicates = deduplicate_content_rows(
                instagram_story_rows,
                "instagram",
                "story",
            )
            combined_breakdown["duplicates_skipped"]["instagram"] += (
                story_duplicates
            )

            feed_uploaded = bool(instagram_post_rows)
            stories_uploaded = bool(instagram_story_rows)
            existing_instagram_content = []
            if feed_uploaded != stories_uploaded:
                existing_instagram_content = self.existing_social_content_posts(
                    conn,
                    client_id,
                    period_id,
                    "instagram",
                )

            if feed_uploaded:
                instagram_posts = summarize_posts(
                    instagram_post_rows,
                    "post",
                    "instagram",
                )
            else:
                instagram_posts = summarize_post_objects(
                    [
                        post
                        for post in existing_instagram_content
                        if not self.is_story_post(post)
                    ],
                    "post",
                )

            if stories_uploaded:
                instagram_stories = summarize_posts(
                    instagram_story_rows,
                    "story",
                    "instagram",
                )
            else:
                instagram_stories = summarize_post_objects(
                    [
                        post
                        for post in existing_instagram_content
                        if self.is_story_post(post)
                    ],
                    "story",
                )
            instagram_summary = self.combine_post_summaries(
                instagram_posts,
                instagram_stories,
            )
            instagram_summary["uploaded"] = bool(
                feed_uploaded or stories_uploaded
            )
            instagram_summary["posts_uploaded"] = feed_uploaded
            instagram_summary["stories_uploaded"] = stories_uploaded
            instagram_summary["imported_count"] = (
                len(instagram_posts.get("raw_posts") or [])
                if feed_uploaded
                else 0
            ) + (
                len(instagram_stories.get("raw_posts") or [])
                if stories_uploaded
                else 0
            )

            post_summaries = {"instagram": instagram_summary}
            legacy_slots = {
                "facebook": "fb_post",
                "tiktok": "tt_post",
                "youtube": "yt_post",
                "linkedin": None,
                "threads": None,
            }
            for platform, legacy_slot in legacy_slots.items():
                platform_rows = (
                    combined_rows[platform]
                    if "all_content" in parsed_files
                    else (
                        parsed_files.get(legacy_slot, {}).get("rows", [])
                        if legacy_slot
                        else []
                    )
                )
                fallback = default_content_type(platform)
                summary = summarize_posts(
                    platform_rows,
                    fallback,
                    platform,
                )
                summary["uploaded"] = bool(platform_rows)
                summary["posts_uploaded"] = bool(platform_rows)
                summary["stories_uploaded"] = False
                summary["post_count"] = summary["totals"]["count"]
                summary["story_count"] = 0
                summary["imported_count"] = len(summary.get("raw_posts") or [])
                post_summaries[platform] = summary

            if "all_content" not in parsed_files:
                for platform, legacy_slot in legacy_slots.items():
                    combined_breakdown["detected"][platform] = len(
                        parsed_files.get(legacy_slot, {}).get("rows", [])
                        if legacy_slot
                        else []
                    )
                combined_breakdown["detected"]["instagram"] = len(
                    parsed_files.get("ig_post", {}).get("rows", [])
                )

            combined_breakdown["detected"]["instagram"] += len(
                parsed_files.get("ig_story", {}).get("rows", [])
            )
            combined_breakdown["imported"] = {
                platform: summary.get(
                    "imported_count",
                    len(summary.get("raw_posts") or []),
                )
                for platform, summary in post_summaries.items()
            }
            combined_breakdown["skipped"] = {
                platform: combined_breakdown["duplicates_skipped"].get(
                    platform,
                    0,
                )
                for platform in PLATFORM_TABLES
            }
            combined_breakdown["content_type_counts"] = {
                platform: dict(summary.get("content_type_counts") or {})
                for platform, summary in post_summaries.items()
            }
            combined_breakdown["platforms"] = {
                platform: {
                    "detected": combined_breakdown["detected"].get(
                        platform,
                        0,
                    ),
                    "imported": combined_breakdown["imported"].get(
                        platform,
                        0,
                    ),
                    "skipped": combined_breakdown["skipped"].get(
                        platform,
                        0,
                    ),
                    "content_types": combined_breakdown[
                        "content_type_counts"
                    ].get(platform, {}),
                }
                for platform in PLATFORM_TABLES
            }
            reports = self.upsert_platform_reports(
                conn,
                client_id,
                period_id,
                profile_ids,
                parsed_files.get("account", {}).get("rows", []),
                post_summaries,
                parsed_files,
            )
            competitor_count = self.upsert_competitors(
                conn,
                client_id,
                period_id,
                parsed_files.get("competitor", {}).get("rows", []),
            )
            competitor_content_count = self.upsert_competitor_content(
                conn,
                client_id,
                period_id,
                parsed_files.get("competitor_content", {}).get("rows", []),
            )
            kpi_count = self.upsert_kpi_results_from_reports(conn, client_id, period_id, reports)
            try:
                from dashboard.services.report_editor import (
                    ReportEditorService,
                    reapply_field_overrides,
                )
            except ModuleNotFoundError:
                from services.report_editor import (
                    ReportEditorService,
                    reapply_field_overrides,
                )
            reapply_field_overrides(
                conn,
                client_id,
                period_id,
                scopes={"field"},
            )
            editor_service = ReportEditorService.__new__(
                ReportEditorService
            )
            editor_service._refresh_calculated_data(
                conn,
                client_id,
                period_id,
            )
            reapply_field_overrides(
                conn,
                client_id,
                period_id,
                scopes={"derived"},
            )
            conn.execute(
                text("UPDATE etl_runs SET finished_at = now(), status = 'success' WHERE id = :run_id"),
                {"run_id": run_id},
            )

        warnings = sum(len(item.get("warnings") or []) for item in file_results)
        return {
            "period": {"id": period_id, "label": period_label, "start": period_start, "end": period_end},
            "summary": {
                "uploaded": len(parsed_files),
                "expected": len(PRIMARY_CSV_IMPORT_SLOTS),
                "missing_files": missing_files,
                "warnings": warnings,
                "platform_reports": reports,
                "competitor_rows": competitor_count,
                "competitor_content_rows": competitor_content_count,
                "kpi_results": kpi_count,
                "content_breakdown": combined_breakdown,
            },
            "files": file_results,
        }

    def ensure_report_period(self, conn, client_id, period_start, period_end, period_label):
        row = conn.execute(
            text(
                """
                INSERT INTO report_periods (client_id, period_start, period_end, period_label)
                VALUES (:client_id, :period_start, :period_end, :period_label)
                ON CONFLICT (client_id, period_start, period_end)
                DO UPDATE SET period_label = EXCLUDED.period_label
                RETURNING id
                """
            ),
            {
                "client_id": client_id,
                "period_start": period_start,
                "period_end": period_end,
                "period_label": period_label,
            },
        ).mappings().one()
        return row["id"]

    def create_import_run(self, conn, client_id, period_id, parsed_files, missing_files):
        row = conn.execute(
            text(
                """
                INSERT INTO etl_runs (client_id, report_period_id, source, status, metadata)
                VALUES (:client_id, :period_id, 'fanpage_karma_csv', 'running', CAST(:metadata AS JSONB))
                RETURNING id
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "metadata": json.dumps(
                    {
                        "files": {slot: data["filename"] for slot, data in parsed_files.items()},
                        "missing_files": missing_files,
                    }
                ),
            },
        ).mappings().one()
        return row["id"]

    def upsert_account_profiles(self, conn, client_id, rows):
        existing_profiles = conn.execute(
            text(
                """
                SELECT DISTINCT ON (platform)
                    platform,
                    id
                FROM client_social_profiles
                WHERE client_id = :client_id
                  AND is_active = TRUE
                ORDER BY platform, updated_at DESC, created_at DESC
                """
            ),
            {"client_id": client_id},
        ).mappings()
        profile_ids = {
            row["platform"]: row["id"]
            for row in existing_profiles
        }
        flags = {platform: False for platform in PLATFORM_TABLES}
        for row in rows:
            platform = platform_from_row(row)
            profile_source_id = row.get("Profile-ID")
            if not platform or not profile_source_id:
                continue
            flags[platform] = True
            profile = conn.execute(
                text(
                    """
                    INSERT INTO client_social_profiles (
                        client_id, platform, source, source_profile_id,
                        profile_name, profile_url, image_url, raw_profile
                    )
                    VALUES (
                        :client_id, :platform, 'fanpage_karma', :source_profile_id,
                        :profile_name, :profile_url, :image_url, CAST(:raw_profile AS JSONB)
                    )
                    ON CONFLICT (source, platform, source_profile_id)
                    DO UPDATE SET
                        client_id = EXCLUDED.client_id,
                        profile_name = EXCLUDED.profile_name,
                        profile_url = EXCLUDED.profile_url,
                        image_url = EXCLUDED.image_url,
                        raw_profile = EXCLUDED.raw_profile,
                        is_active = TRUE,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "client_id": client_id,
                    "platform": platform,
                    "source_profile_id": profile_source_id,
                    "profile_name": row.get("Profile"),
                    "profile_url": row.get("Link"),
                    "image_url": row.get("Image Link"),
                    "raw_profile": json.dumps(row),
                },
            ).mappings().one()
            profile_ids[platform] = profile["id"]
        conn.execute(
            text(
                """
                UPDATE clients
                SET has_instagram = has_instagram OR :instagram,
                    has_facebook = has_facebook OR :facebook,
                    has_tiktok = has_tiktok OR :tiktok,
                    has_youtube = has_youtube OR :youtube,
                    has_linkedin = has_linkedin OR :linkedin,
                    has_threads = has_threads OR :threads,
                    updated_at = now()
                WHERE id = :client_id
                """
            ),
            {"client_id": client_id, **flags},
        )
        return profile_ids

    def content_profile_platforms(self, conn, client_id: str) -> dict[str, str]:
        rows = conn.execute(
            text(
                """
                SELECT source_profile_id, platform
                FROM client_social_profiles
                WHERE client_id = :client_id
                  AND is_active = TRUE
                  AND source_profile_id IS NOT NULL
                """
            ),
            {"client_id": client_id},
        ).mappings()
        return {
            str(row["source_profile_id"]).strip(): row["platform"]
            for row in rows
            if str(row["source_profile_id"] or "").strip()
        }

    def store_raw_csv_rows(self, conn, run_id, client_id, profile_ids, parsed_files):
        for slot, data in parsed_files.items():
            platform = CSV_IMPORT_SLOTS[slot]["platform"]
            endpoint = f"csv_import/{slot}"
            for row in data["rows"]:
                row_platform = platform or (
                    platform_from_content_row(row)
                    if slot in {"all_content", "competitor_content"}
                    else platform_from_row(row)
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO raw_api_responses (
                            run_id, client_id, profile_id, source, platform,
                            endpoint, request_params, response
                        )
                        VALUES (
                            :run_id, :client_id, :profile_id, 'fanpage_karma_csv',
                            :platform, :endpoint, CAST(:request_params AS JSONB), CAST(:response AS JSONB)
                        )
                        """
                    ),
                    {
                        "run_id": run_id,
                        "client_id": client_id,
                        "profile_id": profile_ids.get(row_platform),
                        "platform": row_platform,
                        "endpoint": endpoint,
                        "request_params": json.dumps({"filename": data["filename"], "slot": slot}),
                        "response": json.dumps(row),
                    },
                )

    def combine_post_summaries(self, post_summary, story_summary):
        content_type_counts = dict(post_summary.get("content_type_counts") or {})
        for content_type, count in (story_summary.get("content_type_counts") or {}).items():
            content_type_counts[content_type] = content_type_counts.get(content_type, 0) + count
        combined = {
            "top_posts": post_summary["top_posts"],
            "low_posts": post_summary["low_posts"],
            "raw_posts": post_summary["raw_posts"] + story_summary["raw_posts"],
            "totals": {},
            "story_count": story_summary["totals"]["count"],
            "post_count": post_summary["totals"]["count"],
            "content_type_counts": content_type_counts,
        }
        for key in (
            "likes",
            "comments",
            "shares",
            "saves",
            "reposts",
            "reactions",
            "reach",
            "views",
            "engagement",
            "count",
        ):
            combined["totals"][key] = post_summary["totals"].get(key, 0) + story_summary["totals"].get(key, 0)
        return combined

    @staticmethod
    def is_story_post(post: dict) -> bool:
        content_type = str(post.get("content_type") or "").strip().lower()
        permalink = str(post.get("permalink") or "").strip().lower()
        return "story" in content_type or "/stories/" in permalink

    def existing_social_content_posts(
        self,
        conn,
        client_id,
        period_id,
        platform,
    ) -> list[dict]:
        rows = conn.execute(
            text(
                """
                SELECT
                    post_id, published_at, caption, permalink, image_url,
                    content_type, likes, comments, shares, saves, reposts,
                    reactions, views, reach, profile_visits,
                    total_engagement, engagement_rate
                FROM social_content_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND platform = :platform
                  AND performance_bucket = 'all'
                ORDER BY published_at ASC NULLS LAST, created_at ASC
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
            },
        ).mappings()
        return [dict(row) for row in rows]

    def upsert_platform_reports(self, conn, client_id, period_id, profile_ids, account_rows, post_summaries, parsed_files):
        account_by_platform = {platform_from_row(row): row for row in account_rows if platform_from_row(row)}
        reports = {}
        for platform, table in PLATFORM_TABLES.items():
            account = account_by_platform.get(platform)
            if not account and not post_summaries.get(platform, {}).get("totals", {}).get("count"):
                continue
            summary = post_summaries.get(platform, {"totals": {}, "top_posts": [], "low_posts": []})
            totals = summary.get("totals", {})
            content_uploaded = bool(summary.get("uploaded"))
            content_has_rows = bool(summary.get("raw_posts"))
            content_type_counts = summary.get("content_type_counts") or {}
            posts_uploaded = bool(summary.get("posts_uploaded"))
            stories_uploaded = bool(summary.get("stories_uploaded"))
            uploaded_post_count = summary.get("post_count", totals.get("count"))
            account_likes = number_from(account or {}, "Number of Likes")
            account_comments = number_from(account or {}, "Number of comments")
            total_engagement = totals.get("engagement") if content_uploaded else None
            if total_engagement is None:
                total_engagement = sum_optional(account_likes, account_comments)
            existing_report = conn.execute(
                text(
                    f"""
                    SELECT id, profile_id, total_engagement,
                           engagement_rate
                    FROM {table}
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                    ORDER BY
                        (profile_id IS NOT NULL) DESC,
                        updated_at DESC,
                        created_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "client_id": client_id,
                    "period_id": period_id,
                },
            ).mappings().first()
            base = {
                "client_id": client_id,
                "profile_id": (
                    profile_ids.get(platform)
                    or (
                        existing_report.get("profile_id")
                        if existing_report
                        else None
                    )
                ),
                "period_id": period_id,
                "existing_report_id": (
                    existing_report.get("id")
                    if existing_report
                    else None
                ),
                "followers": parse_number((account or {}).get("Follower")),
                "follower_growth": number_from(
                    account or {},
                    "Followers growth absolute",
                    "Follower growth absolute",
                    "Followers Growth Absolute",
                    "Follower Growth Absolute",
                    "Followers growth",
                    "Follower growth",
                    "Net growth",
                    "Net Growth",
                ),
                "follower_growth_rate": percent_from(
                    account or {},
                    "Followers growth in %",
                    "Follower growth in %",
                    "Followers Growth in %",
                    "Follower Growth in %",
                    "Followers growth %",
                    "Follower growth %",
                    "Growth Rate",
                    "Growth rate",
                ),
                "follows": number_from(
                    account or {},
                    "New Followers",
                    "New Follower",
                    "New Followwer",
                    "New followers",
                    "Follows",
                    "Followers gained",
                    "New Subscribers",
                    "New Subscriber",
                ),
                "unfollows": number_from(
                    account or {},
                    "Unfollows",
                    "Unfollow",
                    "Lost Followers",
                    "Lost followers",
                    "Followers lost",
                    "Subscribers lost",
                    "Lost Subscribers",
                ),
                "posts": (
                    uploaded_post_count
                    if posts_uploaded
                    else parse_number((account or {}).get("Number of posts"))
                ),
                "engagement_rate": engagement_percent(
                    (account or {}).get("Engagement")
                ),
                "likes": account_likes if account_likes is not None else (totals.get("likes") if content_uploaded else None),
                "comments": account_comments if account_comments is not None else (totals.get("comments") if content_uploaded else None),
                "shares": totals.get("shares") if content_uploaded else None,
                "saves": totals.get("saves") if content_uploaded else None,
                "reposts": totals.get("reposts") if content_uploaded else None,
                "reactions": totals.get("reactions") if content_uploaded else None,
                "reach": totals.get("reach") if content_uploaded else None,
                "views": totals.get("views") if content_uploaded else None,
                "engagement": total_engagement,
                "reels_posts": content_type_counts.get("reel", 0) if posts_uploaded else None,
                "carousel_posts": content_type_counts.get("carousel", 0) if posts_uploaded else None,
                "single_posts": content_type_counts.get("image", 0) if posts_uploaded else None,
                "story_posts": content_type_counts.get("story", 0) if stories_uploaded else None,
                "video_posts": (
                    sum(content_type_counts.get(kind, 0) for kind in ("video", "short"))
                    if posts_uploaded
                    else None
                ),
                "photo_posts": (
                    sum(content_type_counts.get(kind, 0) for kind in ("photo", "image", "carousel"))
                    if posts_uploaded
                    else None
                ),
                "text_posts": content_type_counts.get("text", 0) if posts_uploaded else None,
                "content_type_breakdown": (
                    json.dumps(content_type_counts) if posts_uploaded else None
                ),
                "shorts_posts": content_type_counts.get("short", 0) if posts_uploaded else None,
                "long_form_posts": content_type_counts.get("video", 0) if posts_uploaded else None,
                "content_has_rows": content_has_rows,
                "top_posts": (
                    json.dumps(json_safe(summary.get("top_posts") or []))
                    if content_has_rows
                    else None
                ),
                "low_posts": (
                    json.dumps(json_safe(summary.get("low_posts") or []))
                    if content_has_rows
                    else None
                ),
                "raw_sections": json.dumps(
                    {
                        "account": account,
                        "post_rows": len(summary.get("raw_posts") or []),
                        "files": {slot: data["filename"] for slot, data in parsed_files.items()},
                    }
                ),
            }
            if (
                base["engagement_rate"] is None
                and content_uploaded
                and existing_report
                and existing_report.get("engagement_rate") is not None
                and existing_report.get("total_engagement") not in (None, 0)
                and total_engagement is not None
            ):
                base["engagement_rate"] = (
                    float(existing_report["engagement_rate"])
                    * float(total_engagement)
                    / float(existing_report["total_engagement"])
                )
            if platform == "youtube":
                report_id = self.upsert_youtube_report(conn, table, base)
            elif platform == "tiktok":
                report_id = self.upsert_tiktok_report(conn, table, base)
            elif platform in {"linkedin", "threads"}:
                report_id = self.upsert_extended_social_report(conn, table, base)
            else:
                report_id = self.upsert_meta_report(conn, table, base)
            if content_has_rows:
                self.upsert_social_content_reports(conn, client_id, period_id, platform, profile_ids.get(platform), summary)
            reports[platform] = {"report_id": report_id, **base}
        return reports

    def upsert_social_content_reports(self, conn, client_id, period_id, platform, profile_id, summary):
        post_groups = [
            ("all", summary.get("raw_posts") or []),
            ("top", summary.get("top_posts") or []),
            ("low", summary.get("low_posts") or []),
        ]
        for bucket, posts in post_groups:
            for index, post in enumerate(posts, start=1):
                self.insert_social_content_report(
                    conn,
                    client_id,
                    period_id,
                    platform,
                    profile_id,
                    bucket,
                    index,
                    post,
                )
            post_ids = [
                post.get("post_id")
                for post in posts
                if post.get("post_id")
            ]
            delete_params = {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
                "performance_bucket": bucket,
            }
            if post_ids:
                conn.execute(
                    text(
                        """
                        DELETE FROM social_content_reports
                        WHERE client_id = :client_id
                          AND report_period_id = :period_id
                          AND platform = :platform
                          AND performance_bucket = :performance_bucket
                          AND NOT (post_id = ANY(:post_ids))
                        """
                    ),
                    {**delete_params, "post_ids": post_ids},
                )
            else:
                conn.execute(
                    text(
                        """
                        DELETE FROM social_content_reports
                        WHERE client_id = :client_id
                          AND report_period_id = :period_id
                          AND platform = :platform
                          AND performance_bucket = :performance_bucket
                        """
                    ),
                    delete_params,
                )

    def insert_social_content_report(self, conn, client_id, period_id, platform, profile_id, bucket, rank, post):
        conn.execute(
            text(
                """
                INSERT INTO social_content_reports (
                    client_id, profile_id, report_period_id, platform, source,
                    post_id, published_at, caption, permalink, image_url,
                    content_type, content_rank, performance_bucket,
                    likes, comments, shares, saves, reposts, reactions,
                    views, reach, profile_visits, total_engagement, engagement_rate,
                    raw_metrics
                )
                VALUES (
                    :client_id, :profile_id, :period_id, :platform, 'fanpage_karma_csv',
                    :post_id, :published_at, :caption, :permalink, :image_url,
                    :content_type, :content_rank, :performance_bucket,
                    :likes, :comments, :shares, :saves, :reposts, :reactions,
                    :views, :reach, :profile_visits, :total_engagement, :engagement_rate,
                    CAST(:raw_metrics AS JSONB)
                )
                ON CONFLICT (
                    client_id, platform, report_period_id,
                    performance_bucket, post_id
                )
                DO UPDATE SET
                    profile_id = EXCLUDED.profile_id,
                    source = EXCLUDED.source,
                    published_at = EXCLUDED.published_at,
                    caption = EXCLUDED.caption,
                    permalink = EXCLUDED.permalink,
                    image_url = EXCLUDED.image_url,
                    content_type = EXCLUDED.content_type,
                    content_rank = EXCLUDED.content_rank,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    shares = EXCLUDED.shares,
                    saves = EXCLUDED.saves,
                    reposts = EXCLUDED.reposts,
                    reactions = EXCLUDED.reactions,
                    views = EXCLUDED.views,
                    reach = EXCLUDED.reach,
                    profile_visits = EXCLUDED.profile_visits,
                    total_engagement = EXCLUDED.total_engagement,
                    engagement_rate = EXCLUDED.engagement_rate,
                    raw_metrics = EXCLUDED.raw_metrics,
                    updated_at = now()
                """
            ),
            {
                "client_id": client_id,
                "profile_id": profile_id,
                "period_id": period_id,
                "platform": platform,
                "post_id": post.get("post_id"),
                "published_at": post.get("published_at"),
                "caption": post.get("caption"),
                "permalink": post.get("permalink"),
                "image_url": post.get("image_url"),
                "content_type": post.get("content_type"),
                "content_rank": rank,
                "performance_bucket": bucket,
                "likes": post.get("likes"),
                "comments": post.get("comments"),
                "shares": post.get("shares"),
                "saves": post.get("saves"),
                "reposts": post.get("reposts"),
                "reactions": post.get("reactions"),
                "views": post.get("views"),
                "reach": post.get("reach"),
                "profile_visits": post.get("profile_visits"),
                "total_engagement": post.get("total_engagement"),
                "engagement_rate": post.get("engagement_rate"),
                "raw_metrics": json.dumps(json_safe(post)),
            },
        )

    def upsert_meta_report(self, conn, table, data):
        if table == "instagram_reports":
            component_columns = ", saves, reposts"
            component_values = ", :saves, :reposts"
            component_update = """
                        saves = COALESCE(:saves, saves),
                        reposts = COALESCE(:reposts, reposts),
            """
            component_conflict_update = f"""
                    saves = COALESCE(EXCLUDED.saves, {table}.saves),
                    reposts = COALESCE(EXCLUDED.reposts, {table}.reposts),
            """
        else:
            component_columns = ", reactions"
            component_values = ", :reactions"
            component_update = """
                        reactions = COALESCE(:reactions, reactions),
            """
            component_conflict_update = f"""
                    reactions = COALESCE(
                        EXCLUDED.reactions,
                        {table}.reactions
                    ),
            """
        if data.get("existing_report_id"):
            row = conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET
                        profile_id = COALESCE(:profile_id, profile_id),
                        total_followers = COALESCE(:followers, total_followers),
                        follower_growth = COALESCE(:follower_growth, follower_growth),
                        follower_growth_rate = COALESCE(:follower_growth_rate, follower_growth_rate),
                        follows = COALESCE(:follows, follows),
                        unfollows = COALESCE(:unfollows, unfollows),
                        reach = COALESCE(:reach, reach),
                        impressions = COALESCE(:views, impressions),
                        total_engagement = COALESCE(:engagement, total_engagement),
                        engagement_rate = COALESCE(:engagement_rate, engagement_rate),
                        likes = COALESCE(:likes, likes),
                        comments = COALESCE(:comments, comments),
                        shares = COALESCE(:shares, shares),
                        {component_update}
                        total_posts = COALESCE(:posts, total_posts),
                        reels_posts = COALESCE(:reels_posts, reels_posts),
                        carousel_posts = COALESCE(:carousel_posts, carousel_posts),
                        single_posts = COALESCE(:single_posts, single_posts),
                        story_posts = COALESCE(:story_posts, story_posts),
                        top_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:top_posts, '[]') AS JSONB)
                            ELSE top_posts
                        END,
                        low_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:low_posts, '[]') AS JSONB)
                            ELSE low_posts
                        END,
                        raw_sections = COALESCE(raw_sections, '{{}}'::jsonb)
                            || jsonb_strip_nulls(CAST(:raw_sections AS JSONB)),
                        updated_at = now()
                    WHERE id = :existing_report_id
                    RETURNING id
                    """
                ),
                data,
            ).mappings().one()
            return row["id"]
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_followers, follower_growth, follower_growth_rate,
                    follows, unfollows, reach, impressions, total_engagement,
                    engagement_rate, likes, comments, shares, total_posts,
                    reels_posts, carousel_posts, single_posts, story_posts,
                    top_posts, low_posts, raw_sections
                    {component_columns}
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :follower_growth, :follower_growth_rate,
                    :follows, :unfollows, :reach, :views, :engagement,
                    :engagement_rate, :likes, :comments, :shares, :posts,
                    :reels_posts, :carousel_posts, :single_posts, :story_posts,
                    CAST(COALESCE(:top_posts, '[]') AS JSONB), CAST(COALESCE(:low_posts, '[]') AS JSONB),
                    CAST(:raw_sections AS JSONB)
                    {component_values}
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_followers = COALESCE(EXCLUDED.total_followers, {table}.total_followers),
                    follower_growth = COALESCE(EXCLUDED.follower_growth, {table}.follower_growth),
                    follower_growth_rate = COALESCE(EXCLUDED.follower_growth_rate, {table}.follower_growth_rate),
                    follows = COALESCE(EXCLUDED.follows, {table}.follows),
                    unfollows = COALESCE(EXCLUDED.unfollows, {table}.unfollows),
                    reach = COALESCE(EXCLUDED.reach, {table}.reach),
                    impressions = COALESCE(EXCLUDED.impressions, {table}.impressions),
                    total_engagement = COALESCE(EXCLUDED.total_engagement, {table}.total_engagement),
                    engagement_rate = COALESCE(EXCLUDED.engagement_rate, {table}.engagement_rate),
                    likes = COALESCE(EXCLUDED.likes, {table}.likes),
                    comments = COALESCE(EXCLUDED.comments, {table}.comments),
                    shares = COALESCE(EXCLUDED.shares, {table}.shares),
                    {component_conflict_update}
                    total_posts = COALESCE(EXCLUDED.total_posts, {table}.total_posts),
                    reels_posts = COALESCE(EXCLUDED.reels_posts, {table}.reels_posts),
                    carousel_posts = COALESCE(EXCLUDED.carousel_posts, {table}.carousel_posts),
                    single_posts = COALESCE(EXCLUDED.single_posts, {table}.single_posts),
                    story_posts = COALESCE(EXCLUDED.story_posts, {table}.story_posts),
                    top_posts = CASE WHEN :content_has_rows THEN EXCLUDED.top_posts ELSE {table}.top_posts END,
                    low_posts = CASE WHEN :content_has_rows THEN EXCLUDED.low_posts ELSE {table}.low_posts END,
                    raw_sections = EXCLUDED.raw_sections,
                    updated_at = now()
                RETURNING id
                """
            ),
            data,
        ).mappings().one()
        return row["id"]

    def upsert_tiktok_report(self, conn, table, data):
        if data.get("existing_report_id"):
            row = conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET
                        profile_id = COALESCE(:profile_id, profile_id),
                        total_followers = COALESCE(:followers, total_followers),
                        follower_growth = COALESCE(:follower_growth, follower_growth),
                        follower_growth_rate = COALESCE(:follower_growth_rate, follower_growth_rate),
                        follows = COALESCE(:follows, follows),
                        unfollows = COALESCE(:unfollows, unfollows),
                        total_views = COALESCE(:views, total_views),
                        reach = COALESCE(:reach, reach),
                        total_engagement = COALESCE(:engagement, total_engagement),
                        engagement_rate = COALESCE(:engagement_rate, engagement_rate),
                        likes = COALESCE(:likes, likes),
                        comments = COALESCE(:comments, comments),
                        shares = COALESCE(:shares, shares),
                        saves = COALESCE(:saves, saves),
                        total_posts = COALESCE(:posts, total_posts),
                        video_posts = COALESCE(:video_posts, video_posts),
                        top_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:top_posts, '[]') AS JSONB)
                            ELSE top_posts
                        END,
                        low_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:low_posts, '[]') AS JSONB)
                            ELSE low_posts
                        END,
                        raw_sections = COALESCE(raw_sections, '{{}}'::jsonb)
                            || jsonb_strip_nulls(CAST(:raw_sections AS JSONB)),
                        updated_at = now()
                    WHERE id = :existing_report_id
                    RETURNING id
                    """
                ),
                data,
            ).mappings().one()
            return row["id"]
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_followers, follower_growth, follower_growth_rate,
                    follows, unfollows, total_views, reach, total_engagement,
                    engagement_rate, likes, comments, shares, total_posts,
                    video_posts, saves, top_posts, low_posts, raw_sections
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :follower_growth, :follower_growth_rate,
                    :follows, :unfollows, :views, :reach, :engagement,
                    :engagement_rate, :likes, :comments, :shares, :posts,
                    :video_posts, :saves, CAST(COALESCE(:top_posts, '[]') AS JSONB), CAST(COALESCE(:low_posts, '[]') AS JSONB),
                    CAST(:raw_sections AS JSONB)
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_followers = COALESCE(EXCLUDED.total_followers, {table}.total_followers),
                    follower_growth = COALESCE(EXCLUDED.follower_growth, {table}.follower_growth),
                    follower_growth_rate = COALESCE(EXCLUDED.follower_growth_rate, {table}.follower_growth_rate),
                    follows = COALESCE(EXCLUDED.follows, {table}.follows),
                    unfollows = COALESCE(EXCLUDED.unfollows, {table}.unfollows),
                    total_views = COALESCE(EXCLUDED.total_views, {table}.total_views),
                    reach = COALESCE(EXCLUDED.reach, {table}.reach),
                    total_engagement = COALESCE(EXCLUDED.total_engagement, {table}.total_engagement),
                    engagement_rate = COALESCE(EXCLUDED.engagement_rate, {table}.engagement_rate),
                    likes = COALESCE(EXCLUDED.likes, {table}.likes),
                    comments = COALESCE(EXCLUDED.comments, {table}.comments),
                    shares = COALESCE(EXCLUDED.shares, {table}.shares),
                    saves = COALESCE(EXCLUDED.saves, {table}.saves),
                    total_posts = COALESCE(EXCLUDED.total_posts, {table}.total_posts),
                    video_posts = COALESCE(EXCLUDED.video_posts, {table}.video_posts),
                    top_posts = CASE WHEN :content_has_rows THEN EXCLUDED.top_posts ELSE {table}.top_posts END,
                    low_posts = CASE WHEN :content_has_rows THEN EXCLUDED.low_posts ELSE {table}.low_posts END,
                    raw_sections = EXCLUDED.raw_sections,
                    updated_at = now()
                RETURNING id
                """
            ),
            data,
        ).mappings().one()
        return row["id"]

    def upsert_extended_social_report(self, conn, table, data):
        if data.get("existing_report_id"):
            row = conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET
                        profile_id = COALESCE(:profile_id, profile_id),
                        total_followers = COALESCE(:followers, total_followers),
                        follower_growth = COALESCE(:follower_growth, follower_growth),
                        follower_growth_rate = COALESCE(:follower_growth_rate, follower_growth_rate),
                        follows = COALESCE(:follows, follows),
                        unfollows = COALESCE(:unfollows, unfollows),
                        total_views = COALESCE(:views, total_views),
                        reach = COALESCE(:reach, reach),
                        impressions = COALESCE(:views, impressions),
                        total_engagement = COALESCE(:engagement, total_engagement),
                        engagement_rate = COALESCE(:engagement_rate, engagement_rate),
                        likes = COALESCE(:likes, likes),
                        comments = COALESCE(:comments, comments),
                        shares = COALESCE(:shares, shares),
                        saves = COALESCE(:saves, saves),
                        reposts = COALESCE(:reposts, reposts),
                        reactions = COALESCE(:reactions, reactions),
                        total_posts = COALESCE(:posts, total_posts),
                        photo_posts = COALESCE(:photo_posts, photo_posts),
                        video_posts = COALESCE(:video_posts, video_posts),
                        text_posts = COALESCE(:text_posts, text_posts),
                        content_type_breakdown = CASE
                            WHEN :content_type_breakdown IS NOT NULL
                            THEN CAST(:content_type_breakdown AS JSONB)
                            ELSE content_type_breakdown
                        END,
                        top_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:top_posts, '[]') AS JSONB)
                            ELSE top_posts
                        END,
                        low_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:low_posts, '[]') AS JSONB)
                            ELSE low_posts
                        END,
                        raw_sections = COALESCE(raw_sections, '{{}}'::jsonb)
                            || jsonb_strip_nulls(CAST(:raw_sections AS JSONB)),
                        updated_at = now()
                    WHERE id = :existing_report_id
                    RETURNING id
                    """
                ),
                data,
            ).mappings().one()
            return row["id"]
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_followers, follower_growth, follower_growth_rate,
                    follows, unfollows, total_views, reach, impressions,
                    total_engagement, engagement_rate, likes, comments, shares,
                    saves, reposts, reactions, total_posts,
                    photo_posts, video_posts, text_posts,
                    content_type_breakdown, top_posts, low_posts, raw_sections
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :follower_growth, :follower_growth_rate,
                    :follows, :unfollows, :views, :reach, :views,
                    :engagement, :engagement_rate, :likes, :comments, :shares,
                    :saves, :reposts, :reactions, :posts,
                    :photo_posts, :video_posts, :text_posts,
                    CAST(COALESCE(:content_type_breakdown, '{{}}') AS JSONB),
                    CAST(COALESCE(:top_posts, '[]') AS JSONB),
                    CAST(COALESCE(:low_posts, '[]') AS JSONB),
                    CAST(:raw_sections AS JSONB)
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_followers = COALESCE(EXCLUDED.total_followers, {table}.total_followers),
                    follower_growth = COALESCE(EXCLUDED.follower_growth, {table}.follower_growth),
                    follower_growth_rate = COALESCE(EXCLUDED.follower_growth_rate, {table}.follower_growth_rate),
                    follows = COALESCE(EXCLUDED.follows, {table}.follows),
                    unfollows = COALESCE(EXCLUDED.unfollows, {table}.unfollows),
                    total_views = COALESCE(EXCLUDED.total_views, {table}.total_views),
                    reach = COALESCE(EXCLUDED.reach, {table}.reach),
                    impressions = COALESCE(EXCLUDED.impressions, {table}.impressions),
                    total_engagement = COALESCE(EXCLUDED.total_engagement, {table}.total_engagement),
                    engagement_rate = COALESCE(EXCLUDED.engagement_rate, {table}.engagement_rate),
                    likes = COALESCE(EXCLUDED.likes, {table}.likes),
                    comments = COALESCE(EXCLUDED.comments, {table}.comments),
                    shares = COALESCE(EXCLUDED.shares, {table}.shares),
                    saves = COALESCE(EXCLUDED.saves, {table}.saves),
                    reposts = COALESCE(EXCLUDED.reposts, {table}.reposts),
                    reactions = COALESCE(EXCLUDED.reactions, {table}.reactions),
                    total_posts = COALESCE(EXCLUDED.total_posts, {table}.total_posts),
                    photo_posts = COALESCE(EXCLUDED.photo_posts, {table}.photo_posts),
                    video_posts = COALESCE(EXCLUDED.video_posts, {table}.video_posts),
                    text_posts = COALESCE(EXCLUDED.text_posts, {table}.text_posts),
                    content_type_breakdown = CASE
                        WHEN :content_type_breakdown IS NOT NULL
                        THEN EXCLUDED.content_type_breakdown
                        ELSE {table}.content_type_breakdown
                    END,
                    top_posts = CASE WHEN :content_has_rows THEN EXCLUDED.top_posts ELSE {table}.top_posts END,
                    low_posts = CASE WHEN :content_has_rows THEN EXCLUDED.low_posts ELSE {table}.low_posts END,
                    raw_sections = EXCLUDED.raw_sections,
                    updated_at = now()
                RETURNING id
                """
            ),
            data,
        ).mappings().one()
        return row["id"]

    def upsert_youtube_report(self, conn, table, data):
        if data.get("existing_report_id"):
            row = conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET
                        profile_id = COALESCE(:profile_id, profile_id),
                        total_subscribers = COALESCE(:followers, total_subscribers),
                        subscriber_growth = COALESCE(:follower_growth, subscriber_growth),
                        subscriber_growth_rate = COALESCE(:follower_growth_rate, subscriber_growth_rate),
                        subscribers_lost = COALESCE(:unfollows, subscribers_lost),
                        total_views = COALESCE(:views, total_views),
                        total_engagement = COALESCE(:engagement, total_engagement),
                        engagement_rate = COALESCE(:engagement_rate, engagement_rate),
                        likes = COALESCE(:likes, likes),
                        comments = COALESCE(:comments, comments),
                        shares = COALESCE(:shares, shares),
                        total_posts = COALESCE(:posts, total_posts),
                        video_posts = COALESCE(:video_posts, video_posts),
                        shorts_posts = COALESCE(:shorts_posts, shorts_posts),
                        long_form_posts = COALESCE(:long_form_posts, long_form_posts),
                        top_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:top_posts, '[]') AS JSONB)
                            ELSE top_posts
                        END,
                        low_posts = CASE
                            WHEN :content_has_rows
                            THEN CAST(COALESCE(:low_posts, '[]') AS JSONB)
                            ELSE low_posts
                        END,
                        raw_sections = COALESCE(raw_sections, '{{}}'::jsonb)
                            || jsonb_strip_nulls(CAST(:raw_sections AS JSONB)),
                        updated_at = now()
                    WHERE id = :existing_report_id
                    RETURNING id
                    """
                ),
                data,
            ).mappings().one()
            return row["id"]
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_subscribers, subscriber_growth, subscriber_growth_rate,
                    subscribers_lost, total_views, total_engagement,
                    engagement_rate, likes, comments, shares, total_posts,
                    video_posts, shorts_posts, long_form_posts,
                    top_posts, low_posts, raw_sections
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :follower_growth, :follower_growth_rate,
                    :unfollows, :views, :engagement,
                    :engagement_rate, :likes, :comments, :shares, :posts,
                    :video_posts, :shorts_posts, :long_form_posts,
                    CAST(COALESCE(:top_posts, '[]') AS JSONB), CAST(COALESCE(:low_posts, '[]') AS JSONB),
                    CAST(:raw_sections AS JSONB)
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_subscribers = COALESCE(EXCLUDED.total_subscribers, {table}.total_subscribers),
                    subscriber_growth = COALESCE(EXCLUDED.subscriber_growth, {table}.subscriber_growth),
                    subscriber_growth_rate = COALESCE(EXCLUDED.subscriber_growth_rate, {table}.subscriber_growth_rate),
                    subscribers_lost = COALESCE(EXCLUDED.subscribers_lost, {table}.subscribers_lost),
                    total_views = COALESCE(EXCLUDED.total_views, {table}.total_views),
                    total_engagement = COALESCE(EXCLUDED.total_engagement, {table}.total_engagement),
                    engagement_rate = COALESCE(EXCLUDED.engagement_rate, {table}.engagement_rate),
                    likes = COALESCE(EXCLUDED.likes, {table}.likes),
                    comments = COALESCE(EXCLUDED.comments, {table}.comments),
                    shares = COALESCE(EXCLUDED.shares, {table}.shares),
                    total_posts = COALESCE(EXCLUDED.total_posts, {table}.total_posts),
                    video_posts = COALESCE(EXCLUDED.video_posts, {table}.video_posts),
                    shorts_posts = COALESCE(EXCLUDED.shorts_posts, {table}.shorts_posts),
                    long_form_posts = COALESCE(EXCLUDED.long_form_posts, {table}.long_form_posts),
                    top_posts = CASE WHEN :content_has_rows THEN EXCLUDED.top_posts ELSE {table}.top_posts END,
                    low_posts = CASE WHEN :content_has_rows THEN EXCLUDED.low_posts ELSE {table}.low_posts END,
                    raw_sections = EXCLUDED.raw_sections,
                    updated_at = now()
                RETURNING id
                """
            ),
            data,
        ).mappings().one()
        return row["id"]

    def upsert_competitors(self, conn, client_id, period_id, rows):
        count = 0
        for row in rows:
            platform = platform_from_row(row)
            if not platform:
                continue
            competitor = conn.execute(
                text(
                    """
                    INSERT INTO client_competitors (client_id, competitor_name, metadata)
                    VALUES (:client_id, :name, CAST(:metadata AS JSONB))
                    ON CONFLICT (client_id, competitor_name)
                    DO UPDATE SET metadata = EXCLUDED.metadata, is_active = TRUE, updated_at = now()
                    RETURNING id
                    """
                ),
                {"client_id": client_id, "name": row.get("Profile"), "metadata": json.dumps({"source": "csv_import"})},
            ).mappings().one()
            profile = conn.execute(
                text(
                    """
                    INSERT INTO competitor_social_profiles (
                        competitor_id, platform, source, source_profile_id,
                        profile_name, profile_url, image_url, raw_profile
                    )
                    VALUES (
                        :competitor_id, :platform, 'fanpage_karma', :source_profile_id,
                        :profile_name, :profile_url, :image_url, CAST(:raw_profile AS JSONB)
                    )
                    ON CONFLICT (competitor_id, platform, source_profile_id)
                    DO UPDATE SET
                        profile_name = EXCLUDED.profile_name,
                        profile_url = EXCLUDED.profile_url,
                        image_url = EXCLUDED.image_url,
                        raw_profile = EXCLUDED.raw_profile,
                        is_active = TRUE,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "competitor_id": competitor["id"],
                    "platform": platform,
                    "source_profile_id": row.get("Profile-ID"),
                    "profile_name": row.get("Profile"),
                    "profile_url": row.get("Link"),
                    "image_url": row.get("Image Link"),
                    "raw_profile": json.dumps(row),
                },
            ).mappings().one()
            conn.execute(
                text(
                    """
                    INSERT INTO competitor_profile_reports (
                        client_id, competitor_id, competitor_profile_id,
                        report_period_id, platform, source, profile_name,
                        total_followers, follower_growth, follower_growth_rate,
                        total_posts, total_engagement,
                        engagement_rate, profile_url, image_url, raw_metrics
                    )
                    VALUES (
                        :client_id, :competitor_id, :profile_id,
                        :period_id, :platform, 'fanpage_karma_csv', :profile_name,
                        :followers, :follower_growth, :follower_growth_rate,
                        :posts, :engagement,
                        :engagement_rate, :profile_url, :image_url, CAST(:raw_metrics AS JSONB)
                    )
                    ON CONFLICT (client_id, platform, report_period_id, profile_name)
                    DO UPDATE SET
                        competitor_id = EXCLUDED.competitor_id,
                        competitor_profile_id = EXCLUDED.competitor_profile_id,
                        total_followers = EXCLUDED.total_followers,
                        follower_growth = COALESCE(
                            EXCLUDED.follower_growth,
                            competitor_profile_reports.follower_growth
                        ),
                        follower_growth_rate = COALESCE(
                            EXCLUDED.follower_growth_rate,
                            competitor_profile_reports.follower_growth_rate
                        ),
                        total_posts = EXCLUDED.total_posts,
                        total_engagement = EXCLUDED.total_engagement,
                        engagement_rate = EXCLUDED.engagement_rate,
                        profile_url = EXCLUDED.profile_url,
                        image_url = EXCLUDED.image_url,
                        raw_metrics = EXCLUDED.raw_metrics,
                        updated_at = now()
                    """
                ),
                {
                    "client_id": client_id,
                    "competitor_id": competitor["id"],
                    "profile_id": profile["id"],
                    "period_id": period_id,
                    "platform": platform,
                    "profile_name": row.get("Profile"),
                    "followers": parse_number(row.get("Follower")),
                    "follower_growth": number_from(
                        row,
                        "Follower Growth (absolute)",
                        "Follower Growth Absolute",
                    ),
                    "follower_growth_rate": percent_from(
                        row,
                        "Follower Growth (in %)",
                        "Follower Growth Rate",
                    ),
                    "posts": parse_number(row.get("Number of posts")),
                    "engagement": numeric(row, "Number of Likes") + numeric(row, "Number of comments"),
                    "engagement_rate": engagement_percent(row.get("Engagement")),
                    "profile_url": row.get("Link"),
                    "image_url": row.get("Image Link"),
                    "raw_metrics": json.dumps(row),
                },
            )
            count += 1
        return count

    def upsert_competitor_content(self, conn, client_id, period_id, rows):
        content_rows = []
        for row in rows:
            post_id = str(row.get("Post-ID", "")).strip()
            if not post_id or post_id.upper() == "SUMME":
                continue
            platform = platform_from_content_row(row)
            profile_name = str(row.get("Profile", "")).strip()
            if not platform or not profile_name:
                continue
            fallback_type = default_content_type(platform)
            post = post_json(row, fallback_type, platform)
            content_rows.append(
                {
                    "platform": platform,
                    "profile_name": profile_name,
                    "source_profile_id": str(row.get("Profile-ID", "")).strip() or None,
                    "post": post,
                    "raw_row": row,
                }
            )

        if not content_rows:
            return 0

        # A new export is the complete source of truth for this period's competitor posts.
        conn.execute(
            text(
                """
                DELETE FROM competitor_content_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                """
            ),
            {"client_id": client_id, "period_id": period_id},
        )

        content_rows.sort(
            key=lambda item: (
                item["platform"],
                item["profile_name"].casefold(),
                -(item["post"].get("total_engagement") or 0),
            )
        )
        ranks = {}
        for item in content_rows:
            platform = item["platform"]
            profile_name = item["profile_name"]
            post = item["post"]
            rank_key = (platform, profile_name.casefold())
            ranks[rank_key] = ranks.get(rank_key, 0) + 1
            content_rank = ranks[rank_key]

            competitor = conn.execute(
                text(
                    """
                    INSERT INTO client_competitors (client_id, competitor_name, metadata)
                    VALUES (:client_id, :name, CAST(:metadata AS JSONB))
                    ON CONFLICT (client_id, competitor_name)
                    DO UPDATE SET metadata = EXCLUDED.metadata, is_active = TRUE, updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "client_id": client_id,
                    "name": profile_name,
                    "metadata": json.dumps({"source": "competitor_content_csv"}),
                },
            ).mappings().one()
            profile = conn.execute(
                text(
                    """
                    INSERT INTO competitor_social_profiles (
                        competitor_id, platform, source, source_profile_id,
                        profile_name, profile_url, image_url, raw_profile
                    )
                    VALUES (
                        :competitor_id, :platform, 'fanpage_karma', :source_profile_id,
                        :profile_name, :profile_url, :image_url, CAST(:raw_profile AS JSONB)
                    )
                    ON CONFLICT (competitor_id, platform, source_profile_id)
                    DO UPDATE SET
                        profile_name = EXCLUDED.profile_name,
                        profile_url = COALESCE(EXCLUDED.profile_url, competitor_social_profiles.profile_url),
                        image_url = COALESCE(EXCLUDED.image_url, competitor_social_profiles.image_url),
                        raw_profile = EXCLUDED.raw_profile,
                        is_active = TRUE,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "competitor_id": competitor["id"],
                    "platform": platform,
                    "source_profile_id": item["source_profile_id"],
                    "profile_name": profile_name,
                    "profile_url": post.get("permalink"),
                    "image_url": post.get("image_url"),
                    "raw_profile": json.dumps(item["raw_row"]),
                },
            ).mappings().one()
            conn.execute(
                text(
                    """
                    INSERT INTO competitor_content_reports (
                        client_id, competitor_id, competitor_profile_id,
                        report_period_id, platform, source, profile_name,
                        post_id, published_at, caption, permalink, image_url,
                        content_type, content_rank, performance_bucket,
                        likes, comments, shares, saves, reposts, reactions,
                        views, reach, profile_visits, total_engagement,
                        engagement_rate, raw_metrics
                    )
                    VALUES (
                        :client_id, :competitor_id, :competitor_profile_id,
                        :period_id, :platform, 'fanpage_karma_csv', :profile_name,
                        :post_id, :published_at, :caption, :permalink, :image_url,
                        :content_type, :content_rank, :performance_bucket,
                        :likes, :comments, :shares, :saves, :reposts, :reactions,
                        :views, :reach, :profile_visits, :total_engagement,
                        :engagement_rate, CAST(:raw_metrics AS JSONB)
                    )
                    """
                ),
                {
                    "client_id": client_id,
                    "competitor_id": competitor["id"],
                    "competitor_profile_id": profile["id"],
                    "period_id": period_id,
                    "platform": platform,
                    "profile_name": profile_name,
                    "post_id": post.get("post_id"),
                    "published_at": post.get("published_at"),
                    "caption": post.get("caption"),
                    "permalink": post.get("permalink"),
                    "image_url": post.get("image_url"),
                    "content_type": post.get("content_type"),
                    "content_rank": content_rank,
                    "performance_bucket": "best_competitor" if content_rank == 1 else "top",
                    "likes": post.get("likes"),
                    "comments": post.get("comments"),
                    "shares": post.get("shares"),
                    "saves": post.get("saves"),
                    "reposts": post.get("reposts"),
                    "reactions": post.get("reactions"),
                    "views": post.get("views"),
                    "reach": post.get("reach"),
                    "profile_visits": post.get("profile_visits"),
                    "total_engagement": post.get("total_engagement"),
                    "engagement_rate": post.get("engagement_rate"),
                    "raw_metrics": json.dumps(item["raw_row"]),
                },
            )
        return len(content_rows)

    def upsert_kpi_results_from_reports(self, conn, client_id, period_id, reports):
        count = 0
        for platform, report in reports.items():
            metric_values = {
                "followers": report.get("followers"),
                "subscribers": report.get("followers"),
                "engagement": report.get("engagement"),
                "reach": report.get("reach"),
                "views": report.get("views"),
                "impressions": report.get("views"),
                "likes": report.get("likes"),
            }
            cumulative_actuals = self.kpi_year_to_date_actuals(
                conn,
                client_id,
                period_id,
                platform,
            )
            for metric_name in PLATFORM_KPI_METRICS[platform]:
                actual = metric_values.get(metric_name)
                if actual is None:
                    continue
                actual_year = cumulative_actuals.get(metric_name, actual)
                target = self.effective_kpi_target(
                    conn,
                    client_id,
                    platform,
                    metric_name,
                    period_id,
                )
                target_month = target.get("target_month")
                target_year = target.get("target_year")
                conn.execute(
                    text(
                        """
                        INSERT INTO kpi_results (
                            client_id, profile_id, report_period_id, kpi_target_id,
                            platform, metric_name, actual_month, actual_year,
                            target_month, target_year, achievement_month, achievement_year,
                            unit, source_report_table, source_report_id
                        )
                        VALUES (
                            :client_id, :profile_id, :period_id, :target_id,
                            :platform, :metric_name, :actual, :actual_year,
                            :target_month, :target_year,
                            CASE WHEN CAST(:target_month AS NUMERIC) IS NOT NULL AND CAST(:target_month AS NUMERIC) <> 0
                                 THEN ROUND((CAST(:actual AS NUMERIC) / CAST(:target_month AS NUMERIC)) * 100, 2)
                                 ELSE NULL END,
                            CASE WHEN CAST(:target_year AS NUMERIC) IS NOT NULL AND CAST(:target_year AS NUMERIC) <> 0
                                 THEN ROUND((CAST(:actual_year AS NUMERIC) / CAST(:target_year AS NUMERIC)) * 100, 2)
                                 ELSE NULL END,
                            :unit, :source_table, :source_id
                        )
                        ON CONFLICT (client_id, platform, report_period_id, metric_name)
                        DO UPDATE SET
                            profile_id = EXCLUDED.profile_id,
                            kpi_target_id = EXCLUDED.kpi_target_id,
                            actual_month = EXCLUDED.actual_month,
                            actual_year = EXCLUDED.actual_year,
                            target_month = EXCLUDED.target_month,
                            target_year = EXCLUDED.target_year,
                            achievement_month = EXCLUDED.achievement_month,
                            achievement_year = EXCLUDED.achievement_year,
                            unit = EXCLUDED.unit,
                            source_report_table = EXCLUDED.source_report_table,
                            source_report_id = EXCLUDED.source_report_id,
                            updated_at = now()
                        """
                    ),
                    {
                        "client_id": client_id,
                        "profile_id": report.get("profile_id"),
                        "period_id": period_id,
                        "target_id": target.get("id"),
                        "platform": platform,
                        "metric_name": metric_name,
                        "actual": actual,
                        "actual_year": actual_year,
                        "target_month": target_month,
                        "target_year": target_year,
                        "unit": target.get("unit"),
                        "source_table": PLATFORM_TABLES[platform],
                        "source_id": report.get("report_id"),
                    },
                )
                count += 1
        return count

    def effective_kpi_target(self, conn, client_id, platform, metric_name, period_id):
        row = conn.execute(
            text(
                """
                WITH selected_period AS (
                    SELECT period_start
                    FROM report_periods
                    WHERE id = :period_id
                      AND client_id = :client_id
                ),
                current_month AS (
                    SELECT kt.id, kt.target_month, kt.target_year, kt.unit
                    FROM kpi_targets kt
                    CROSS JOIN selected_period selected
                    WHERE kt.client_id = :client_id
                      AND kt.platform = :platform
                      AND kt.metric_name = :metric_name
                      AND kt.period_year = EXTRACT(YEAR FROM selected.period_start)
                      AND kt.period_month = EXTRACT(MONTH FROM selected.period_start)
                ),
                latest_yearly AS (
                    SELECT kt.id, kt.target_year, kt.unit
                    FROM kpi_targets kt
                    CROSS JOIN selected_period selected
                    WHERE kt.client_id = :client_id
                      AND kt.platform = :platform
                      AND kt.metric_name = :metric_name
                      AND kt.period_year = EXTRACT(YEAR FROM selected.period_start)
                      AND kt.period_month <= EXTRACT(MONTH FROM selected.period_start)
                      AND kt.target_year IS NOT NULL
                    ORDER BY kt.period_month DESC
                    LIMIT 1
                )
                SELECT
                    COALESCE(current_month.id, latest_yearly.id) AS id,
                    current_month.target_month,
                    COALESCE(current_month.target_year, latest_yearly.target_year) AS target_year,
                    COALESCE(current_month.unit, latest_yearly.unit) AS unit
                FROM (SELECT 1) anchor
                LEFT JOIN current_month ON TRUE
                LEFT JOIN latest_yearly ON TRUE
                """
            ),
            {
                "client_id": client_id,
                "platform": platform,
                "metric_name": metric_name,
                "period_id": period_id,
            },
        ).mappings().one()
        return dict(row)

    def kpi_year_to_date_actuals(self, conn, client_id, period_id, platform):
        metric_fields = CUMULATIVE_KPI_FIELDS.get(platform, {})
        if not metric_fields:
            return {}
        table = PLATFORM_TABLES[platform]
        aggregate_columns = ", ".join(
            f"SUM({field}) FILTER (WHERE report_rank = 1) AS {metric_name}"
            for metric_name, field in metric_fields.items()
        )
        row = conn.execute(
            text(
                f"""
                WITH selected_period AS (
                    SELECT period_start
                    FROM report_periods
                    WHERE id = :period_id
                      AND client_id = :client_id
                ),
                ranked_reports AS (
                    SELECT
                        r.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY r.report_period_id
                            ORDER BY
                                (r.profile_id IS NOT NULL) DESC,
                                r.updated_at DESC,
                                r.created_at DESC
                        ) AS report_rank
                    FROM {table} r
                    JOIN report_periods rp ON rp.id = r.report_period_id
                    CROSS JOIN selected_period selected
                    WHERE r.client_id = :client_id
                      AND EXTRACT(YEAR FROM rp.period_start) = EXTRACT(YEAR FROM selected.period_start)
                      AND rp.period_start <= selected.period_start
                      AND EXISTS (
                          SELECT 1
                          FROM social_content_reports content
                          WHERE content.client_id = r.client_id
                            AND content.report_period_id = r.report_period_id
                            AND content.platform = :platform
                            AND content.performance_bucket = 'all'
                      )
                )
                SELECT {aggregate_columns}
                FROM ranked_reports
                """
            ),
            {"client_id": client_id, "period_id": period_id, "platform": platform},
        ).mappings().one()
        return {
            metric_name: row.get(metric_name)
            for metric_name in metric_fields
            if row.get(metric_name) is not None
        }


def overview_metrics(platform: str, report: dict | None):
    if not report:
        return []
    if platform == "youtube":
        return [
            metric("Subscribers", report.get("total_subscribers")),
            metric("Growth Rate", report.get("subscriber_growth_rate"), "%"),
            metric("Views", report.get("total_views")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    if platform == "tiktok":
        return [
            metric("Followers", report.get("total_followers")),
            metric("Follows", report.get("follows")),
            metric("Growth Rate", report.get("follower_growth_rate"), "%"),
            metric("Views", report.get("total_views")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    if platform == "linkedin":
        return [
            metric("Followers", report.get("total_followers")),
            metric("Follows", report.get("follows")),
            metric("Growth Rate", report.get("follower_growth_rate"), "%"),
            metric("Impressions", report.get("impressions")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    if platform == "threads":
        return [
            metric("Followers", report.get("total_followers")),
            metric("Follows", report.get("follows")),
            metric("Growth Rate", report.get("follower_growth_rate"), "%"),
            metric("Views", report.get("total_views")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    return [
        metric("Followers", report.get("total_followers")),
        metric("Follows", report.get("follows")),
        metric("Growth Rate", report.get("follower_growth_rate"), "%"),
        metric("Reach", report.get("reach")),
        metric("Engagement", report.get("total_engagement")),
        metric("Eng. Rate", report.get("engagement_rate"), "%"),
        metric("Posts", report.get("total_posts")),
    ]


def metric(label: str, value, suffix: str = ""):
    return {"label": label, "value": value, "suffix": suffix}


def kpi_actual_value(platform: str, report: dict | None, metric_name: str):
    if not report:
        return None
    if metric_name == "followers":
        return report.get("total_followers")
    if metric_name == "subscribers":
        return report.get("total_subscribers")
    if metric_name == "engagement":
        return report.get("total_engagement")
    if metric_name == "reach":
        return report.get("reach")
    if metric_name == "views":
        return report.get("total_views") or report.get("views")
    if metric_name == "likes":
        return report.get("likes")
    if metric_name == "impressions":
        return report.get("impressions")
    return None


def achievement(actual, target):
    try:
        actual_number = Decimal(str(actual))
        target_number = Decimal(str(target))
    except Exception:
        return None
    if target_number == 0:
        return None
    return round(float((actual_number / target_number) * 100), 2)


def dashboard_kpi_results(platform: str, report: dict | None, rows: list[dict], targets: list[dict]):
    configured_metrics = sorted(PLATFORM_KPI_METRICS.get(platform, set()))
    rows_by_metric = {row.get("metric_name"): dict(row) for row in rows or []}
    report_period = (report or {}).get("period_start")
    report_year = getattr(report_period, "year", None)
    report_month = getattr(report_period, "month", None)
    result = []
    for metric_name in configured_metrics:
        row = rows_by_metric.get(metric_name) or {"metric_name": metric_name}
        target_candidates = [
            dict(target)
            for target in targets or []
            if target.get("metric_name") == metric_name
            and (
                report_year is None
                or (
                    int(target.get("period_year") or 0) == report_year
                    and int(target.get("period_month") or 0) <= report_month
                )
            )
        ]
        monthly_target = next(
            (target for target in target_candidates if int(target.get("period_month") or 0) == report_month),
            {},
        )
        yearly_target = next(
            (target for target in target_candidates if target.get("target_year") is not None),
            {},
        )
        actual_month = row.get("actual_month")
        if actual_month is None:
            actual_month = kpi_actual_value(platform, report, metric_name)
        actual_year = row.get("actual_year")
        if actual_year is None:
            actual_year = actual_month
        target_month = row.get("target_month")
        if target_month is None:
            target_month = monthly_target.get("target_month")
        target_year = row.get("target_year")
        if target_year is None:
            target_year = monthly_target.get("target_year") or yearly_target.get("target_year")
        achievement_month = row.get("achievement_month")
        if achievement_month is None:
            achievement_month = achievement(actual_month, target_month)
        achievement_year = row.get("achievement_year")
        if achievement_year is None:
            achievement_year = achievement(actual_year, target_year)
        result.append(
            {
                **row,
                "metric_name": metric_name,
                "actual_month": actual_month,
                "actual_year": actual_year,
                "target_month": target_month,
                "target_year": target_year,
                "achievement_month": achievement_month,
                "achievement_year": achievement_year,
                "unit": row.get("unit") or monthly_target.get("unit") or yearly_target.get("unit"),
            }
        )
    return result


def is_missing_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def missing_platform_data(platform: str, report: dict | None, content_missing=None):
    content_missing = content_missing or []
    if not report:
        return {
            "status": "missing",
            "missing_count": len(PLATFORM_DATA_FIELDS.get(platform, [])),
            "total_count": len(PLATFORM_DATA_FIELDS.get(platform, [])),
            "items": [
                {"field": field, "label": label}
                for field, label in PLATFORM_DATA_FIELDS.get(platform, [])
            ],
        }
    fields = PLATFORM_DATA_FIELDS.get(platform, [])
    items = [
        {"field": field, "label": label}
        for field, label in fields
        if is_missing_value(report.get(field))
    ]
    if not ((report.get("top_posts") or []) or (report.get("low_posts") or [])):
        items.append({"field": "content_posts", "label": "Top/low content posts"})
    if not (report.get("competitor_profiles") or []):
        items.append({"field": "competitor_profiles", "label": "Competitor summary"})
    items.extend(content_missing)
    missing_count = len(items)
    total_count = len(fields) + 2 + len(content_missing)
    if missing_count == 0:
        status = "complete"
    elif missing_count == total_count:
        status = "missing"
    else:
        status = "partial"
    return {
        "status": status,
        "missing_count": missing_count,
        "total_count": total_count,
        "items": items,
    }

