from __future__ import annotations

import ipaddress
import json
import mimetypes
import os
import re
import socket
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import text

from dashboard.db import create_db_engine
from dashboard.repositories.dashboard_repository import (
    PLATFORM_DATA_FIELDS,
    PLATFORM_TABLES,
    json_safe,
)
from dashboard.repositories.report_data_lock import lock_report_period
from dashboard.slides_report import SlidesReportRepository, build_mapping


PLATFORM_PREFIXES = {
    "instagram": "IG",
    "facebook": "FB",
    "tiktok": "TK",
    "youtube": "YT",
    "linkedin": "LK",
    "threads": "TH",
}

CONTENT_FIELDS = {
    "published_at": ("Date posted", "datetime"),
    "caption": ("Caption", "text"),
    "permalink": ("Post URL", "url"),
    "image_url": ("Image URL", "url"),
    "content_type": ("Content type", "text"),
    "likes": ("Likes", "number"),
    "comments": ("Comments", "number"),
    "shares": ("Shares", "number"),
    "saves": ("Saves", "number"),
    "reposts": ("Reposts", "number"),
    "reactions": ("Reactions", "number"),
    "views": ("Views", "number"),
    "reach": ("Reach", "number"),
    "profile_visits": ("Profile visits", "number"),
    "total_engagement": ("Total engagement", "number"),
    "engagement_rate": ("Engagement rate", "percent"),
    "performance_bucket": ("Performance bucket", "text"),
    "content_rank": ("Content rank", "number"),
}

COMPETITOR_FIELDS = {
    "profile_name": ("Profile", "text"),
    "total_followers": ("Followers", "number"),
    "follower_growth": ("Follower growth", "number"),
    "follower_growth_rate": ("Growth rate", "percent"),
    "total_posts": ("Posts", "number"),
    "total_engagement": ("Total engagement", "number"),
    "engagement_rate": ("Engagement rate", "percent"),
    "reach": ("Reach", "number"),
    "impressions": ("Impressions", "number"),
    "profile_url": ("Profile URL", "url"),
    "image_url": ("Profile image URL", "url"),
}

KPI_FIELDS = {
    "actual_month": ("Actual month", "number"),
    "actual_year": ("Actual year", "number"),
    "target_month": ("Target month", "number"),
    "target_year": ("Target year", "number"),
    "achievement_month": ("Achievement month", "percent"),
    "achievement_year": ("Achievement year", "percent"),
    "unit": ("Unit", "text"),
}

TREND_FIELDS = {
    "audience_total": ("Audience total", "number"),
    "growth": ("Net growth", "number"),
    "growth_rate": ("Growth rate", "percent"),
    "audience_gained": ("New audience", "number"),
    "audience_lost": ("Lost audience", "number"),
    "total_engagement": ("Total engagement", "number"),
    "engagement_rate": ("Engagement rate", "percent"),
    "reach_or_views": ("Reach or views", "number"),
    "impressions_or_views": ("Impressions or views", "number"),
    "likes": ("Likes", "number"),
    "comments": ("Comments", "number"),
    "shares": ("Shares", "number"),
    "total_posts": ("Total posts", "number"),
}

TREND_SUFFIXES = {
    "audience_total": "TOTAL_FOLLOWERS",
    "growth": "NET_GROWTH",
    "growth_rate": "GROWTH_RATE",
    "audience_gained": "FOLLOWS",
    "audience_lost": "UNFOLLOWS",
    "total_engagement": "ENGAGEMENT",
    "engagement_rate": "ER",
    "reach_or_views": "REACH",
    "impressions_or_views": "IMPR",
    "likes": "LIKES",
    "comments": "COMMENTS",
    "shares": "SHARES",
    "total_posts": "POSTS",
}

REPORT_FIELD_TYPES = {
    "demographics": "json",
    "daily_followers": "json",
    "daily_subscribers": "json",
    "daily_views": "json",
    "daily_engagement": "json",
}

REPORT_ENGAGEMENT_COMPONENTS = {
    "instagram_reports": {
        "likes",
        "comments",
        "shares",
        "saves",
        "reposts",
    },
    "facebook_reports": {
        "likes",
        "comments",
        "shares",
        "reactions",
    },
    "tiktok_reports": {
        "likes",
        "comments",
        "shares",
        "saves",
    },
    "youtube_reports": {
        "likes",
        "comments",
        "shares",
    },
    "linkedin_reports": {
        "likes",
        "comments",
        "shares",
        "reposts",
        "reactions",
    },
    "threads_reports": {
        "likes",
        "comments",
        "shares",
        "reposts",
    },
}

REPORT_AUDIENCE_FIELDS = {
    "instagram_reports": "total_followers",
    "facebook_reports": "total_followers",
    "tiktok_reports": "total_followers",
    "youtube_reports": "total_subscribers",
    "linkedin_reports": "total_followers",
    "threads_reports": "total_followers",
}

REPORT_GROWTH_FIELDS = {
    "instagram_reports": {
        "growth": "follower_growth",
        "rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "audience": "total_followers",
    },
    "facebook_reports": {
        "growth": "follower_growth",
        "rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "audience": "total_followers",
    },
    "tiktok_reports": {
        "growth": "follower_growth",
        "rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "audience": "total_followers",
    },
    "youtube_reports": {
        "growth": "subscriber_growth",
        "rate": "subscriber_growth_rate",
        "gained": None,
        "lost": "subscribers_lost",
        "audience": "total_subscribers",
    },
    "linkedin_reports": {
        "growth": "follower_growth",
        "rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "audience": "total_followers",
    },
    "threads_reports": {
        "growth": "follower_growth",
        "rate": "follower_growth_rate",
        "gained": "follows",
        "lost": "unfollows",
        "audience": "total_followers",
    },
}

CALCULATED_REPORT_FIELDS = {
    "total_engagement",
    "engagement_rate",
    "follower_growth",
    "follower_growth_rate",
    "subscriber_growth_rate",
}

CALCULATED_CONTENT_FIELDS = {
    "total_engagement",
    "engagement_rate",
}

ALLOWED_TABLE_FIELDS = {
    **{
        table: {
            field_name
            for field_name, _label in PLATFORM_DATA_FIELDS[platform]
        }
        for platform, table in PLATFORM_TABLES.items()
    },
    "social_content_reports": set(CONTENT_FIELDS),
    "competitor_content_reports": set(CONTENT_FIELDS)
    | {"profile_name", "content_rank", "performance_bucket"},
    "competitor_profile_reports": set(COMPETITOR_FIELDS),
    "kpi_results": set(KPI_FIELDS),
}

AI_PLACEHOLDER_PARTS = (
    "EXECUTIVE_SUMMARY",
    "KPI_ANALYSIS",
    "PERFORMANCE_INSIGHT",
    "INSIGHT_",
    "SUMMARY_POINT",
    "RECOMMENDATION",
    "ACTION_PLAN",
    "SUCCESS_DRIVER",
    "FAILURE_DRIVER",
    "COMPETITOR_STRATEGY_INSIGHT",
    "BENCHMARK_NOTE",
    "KEY_SUMMARY",
    "GROWTH_TEXT",
    "ENGAGEMENT_TREND_TEXT",
)

WEB_ADS_PREFIXES = (
    "{{WEB_",
    "{{ADS_",
    "{{SSL_",
    "{{DOMAIN_",
)


def is_ai_placeholder(placeholder_key: str) -> bool:
    name = placeholder_key.strip("{}").upper()
    return any(part in name for part in AI_PLACEHOLDER_PARTS)


def decimal_value(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def scaled_rate(
    current_rate,
    old_value,
    new_value,
    fallback_denominator=None,
):
    old_numeric = decimal_value(old_value)
    new_numeric = decimal_value(new_value)
    rate_numeric = (
        None
        if current_rate in (None, "")
        else decimal_value(current_rate)
    )
    if rate_numeric is not None and old_numeric != 0:
        return rate_numeric * new_numeric / old_numeric
    denominator = decimal_value(fallback_denominator)
    if denominator != 0:
        return new_numeric / denominator * Decimal("100")
    return None


def placeholder_aliases(platform: str, field_name: str) -> list[str]:
    prefix = PLATFORM_PREFIXES[platform]
    suffixes = {
        "total_followers": ("TOTAL_FOLLOWERS", "TOTAL_FOL"),
        "total_subscribers": ("TOTAL_SUBSCRIBERS", "TOTAL_SUB"),
        "follower_growth": ("FOLLOWERS_GROWTH", "NET_GROWTH"),
        "subscriber_growth": ("SUBSCRIBER_GROWTH", "NET_GROWTH"),
        "follower_growth_rate": ("FOLLOWERS_GROWTH_RATE", "GROWTH_RATE"),
        "subscriber_growth_rate": ("SUBSCRIBER_GROWTH_RATE", "GROWTH_RATE"),
        "follows": ("FOLLOWS",),
        "unfollows": ("UNFOLLOWS",),
        "subscribers_lost": ("SUBSCRIBERS_LOST",),
        "reach": ("TOTAL_REACH", "REACH"),
        "impressions": ("TOTAL_VIEWS",),
        "total_views": ("TOTAL_VIEWS",),
        "total_engagement": (
            "TOTAL_ENGAGEMENT",
            "TOTAL_ENG",
            "ENGAGEMENT",
        ),
        "engagement_rate": (
            "AVG_ENGAGEMENT_RATE",
            "AVG_ER",
            "ER",
        ),
        "likes": ("TOTAL_LIKES", "LIKES"),
        "comments": ("TOTAL_COMMENTS", "COMMENT", "COMMENTS"),
        "shares": ("TOTAL_SHARES", "SHARE", "SHARES"),
        "saves": ("TOTAL_SAVED", "TOTAL_SAVES"),
        "reposts": ("TOTAL_REPOSTS",),
        "total_posts": ("TOTAL_POSTS",),
        "reels_posts": ("TOTAL_REELS",),
        "carousel_posts": ("TOTAL_CAROUSEL",),
        "single_posts": ("TOTAL_SINGLE",),
        "story_posts": ("TOTAL_STORIES",),
        "video_posts": ("TOTAL_VIDEOS",),
        "shorts_posts": ("TOTAL_SHORTS",),
        "long_form_posts": ("TOTAL_LONG_FORM",),
        "live_posts": ("TOTAL_LIVE",),
        "demographics": ("AUDIENCE_DEMOGRAPHIC",),
    }.get(field_name, ())
    return [f"{{{{{prefix}_{suffix}}}}}" for suffix in suffixes]


def trend_database_fields(platform: str) -> dict[str, str]:
    return {
        "audience_total": (
            "total_subscribers"
            if platform == "youtube"
            else "total_followers"
        ),
        "growth": (
            "subscriber_growth"
            if platform == "youtube"
            else "follower_growth"
        ),
        "growth_rate": (
            "subscriber_growth_rate"
            if platform == "youtube"
            else "follower_growth_rate"
        ),
        "audience_gained": (
            "subscriber_growth"
            if platform == "youtube"
            else "follows"
        ),
        "audience_lost": (
            "subscribers_lost"
            if platform == "youtube"
            else "unfollows"
        ),
        "total_engagement": "total_engagement",
        "engagement_rate": "engagement_rate",
        "reach_or_views": "reach",
        "impressions_or_views": (
            "total_views"
            if platform in {"tiktok", "youtube", "threads"}
            else "impressions"
        ),
        "likes": "likes",
        "comments": "comments",
        "shares": "shares",
        "total_posts": "total_posts",
    }


def trend_placeholder_aliases(
    platform: str,
    trend_index: int,
    trend_key: str,
) -> list[str]:
    suffix = TREND_SUFFIXES[trend_key]
    if platform == "youtube":
        suffix = {
            "audience_total": "TOTAL_SUBSCRIBERS",
            "audience_gained": "SUBSCRIBERS_GAINED",
            "audience_lost": "SUBSCRIBERS_LOST",
            "reach_or_views": "VIEWS",
        }.get(trend_key, suffix)
    prefix = PLATFORM_PREFIXES[platform]
    return [
        f"{{{{M{trend_index}_{prefix}_{suffix}}}}}",
        f"{{{{{prefix}_M{trend_index}_{suffix}}}}}",
        f"{{{{{prefix}_{trend_index}_{suffix}}}}}",
    ]


def clean_actor(value) -> str:
    actor = str(value or "").strip()
    if len(actor) < 2:
        raise ValueError("Editor name must contain at least 2 characters.")
    if len(actor) > 80:
        raise ValueError("Editor name must be 80 characters or fewer.")
    return actor


def validate_public_url(value: str) -> str:
    url = str(value or "").strip()
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http or https.")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("Private or local URLs are not allowed.")
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(hostname, None)
        }
    except socket.gaierror as exc:
        raise ValueError(f"URL hostname could not be resolved: {exc}") from exc
    for address in addresses:
        ip_value = ipaddress.ip_address(address)
        if (
            ip_value.is_private
            or ip_value.is_loopback
            or ip_value.is_link_local
            or ip_value.is_reserved
        ):
            raise ValueError("Private or local URLs are not allowed.")
    return url


def parse_editor_value(value, value_type: str):
    if value in ("", None):
        return None
    if value_type in {"number", "percent"}:
        try:
            number = float(str(value).replace(",", "").replace("%", ""))
        except ValueError as exc:
            raise ValueError(f"Expected a numeric value, received {value!r}.") from exc
        return number
    if value_type == "json":
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except json.JSONDecodeError as exc:
            raise ValueError("JSON value is invalid.") from exc
    if value_type == "datetime":
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Date must use ISO format.") from exc
    if value_type == "url":
        return validate_public_url(str(value))
    return str(value)


def json_parameter(value):
    return json.dumps(json_safe(value), ensure_ascii=False)


class ReportEditorService:
    def __init__(self, engine=None):
        self.engine = engine or create_db_engine()

    def _context(self, conn, client_id: str, period_id: str) -> dict:
        context = conn.execute(
            text(
                """
                SELECT
                    c.id AS client_id,
                    c.client_code,
                    c.client_name,
                    rp.id AS period_id,
                    rp.period_label,
                    rp.period_start,
                    rp.period_end
                FROM clients c
                JOIN report_periods rp ON rp.client_id = c.id
                WHERE c.id = :client_id
                  AND rp.id = :period_id
                """
            ),
            {"client_id": client_id, "period_id": period_id},
        ).mappings().first()
        if not context:
            raise ValueError("Client or report period not found.")
        return json_safe(dict(context))

    def _active_overrides(self, conn, period_id: str) -> list[dict]:
        return [
            json_safe(dict(row))
            for row in conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_overrides
                    WHERE report_period_id = :period_id
                      AND is_active = TRUE
                    ORDER BY updated_at DESC
                    """
                ),
                {"period_id": period_id},
            ).mappings()
        ]

    def _override_index(self, overrides: list[dict]) -> dict[tuple, dict]:
        return {
            (
                row["scope"],
                row["entity_ref"],
                row["override_key"],
            ): row
            for row in overrides
        }

    def _field_item(
        self,
        *,
        section: str,
        table: str,
        row_id,
        field_name: str,
        label: str,
        value,
        value_type: str,
        platform: str | None,
        aliases: list[str],
        overrides: dict,
        extra: dict | None = None,
        override_scope: str = "field",
    ) -> dict:
        entity_ref = f"{table}:{row_id}"
        override = overrides.get(
            (override_scope, entity_ref, field_name)
        )
        return {
            "id": f"field|{table}|{row_id}|{field_name}",
            "kind": "field",
            "override_scope": override_scope,
            "section": section,
            "platform": platform,
            "label": label,
            "field_key": field_name,
            "value_type": value_type,
            "source_value": (
                override.get("source_value")
                if override
                else json_safe(value)
            ),
            "value": (
                override.get("override_value")
                if override
                else json_safe(value)
            ),
            "status": "edited" if override else (
                "missing" if value is None or value == "" else "imported"
            ),
            "override_id": override.get("id") if override else None,
            "edited_by": override.get("edited_by") if override else None,
            "updated_at": override.get("updated_at") if override else None,
            "placeholders": aliases,
            **(extra or {}),
        }

    def _placeholder_item(
        self,
        section: str,
        placeholder_key: str,
        source_value,
        overrides: dict,
    ) -> dict:
        override = overrides.get(
            ("placeholder", "report", placeholder_key)
        )
        return {
            "id": f"placeholder|{placeholder_key}",
            "kind": "placeholder",
            "section": section,
            "platform": None,
            "label": placeholder_key.strip("{}").replace("_", " ").title(),
            "field_key": placeholder_key,
            "value_type": (
                "url" if placeholder_key.endswith("_IMAGE}}") else "text"
            ),
            "source_value": source_value,
            "value": (
                override.get("override_value")
                if override
                else source_value
            ),
            "status": "edited" if override else (
                "missing"
                if source_value in (None, "", "-")
                else "calculated"
            ),
            "override_id": override.get("id") if override else None,
            "edited_by": override.get("edited_by") if override else None,
            "updated_at": override.get("updated_at") if override else None,
            "placeholders": [placeholder_key],
        }

    def get_editor(self, client_id: str, period_id: str) -> dict:
        payload = SlidesReportRepository(self.engine).report_payload(
            client_id,
            period_id,
        )
        mapping = build_mapping(payload)
        with self.engine.begin() as conn:
            context = self._context(conn, client_id, period_id)
            override_rows = self._active_overrides(conn, period_id)
            overrides = self._override_index(override_rows)
            sections: dict[str, list[dict]] = {
                "general": [],
                "instagram": [],
                "facebook": [],
                "tiktok": [],
                "youtube": [],
                "linkedin": [],
                "threads": [],
                "kpi": [],
                "competitor": [],
                "content": [],
                "demographics": [],
                "website_ads": [],
                "advanced": [],
            }

            for placeholder_key in (
                "{{CLIENT_NAME}}",
                "{{AGENCY_NAME}}",
                "{{REPORT_PERIOD}}",
                "{{TOTAL_REACH}}",
                "{{TOTAL_VIEWS}}",
                "{{TOTAL_ENGAGEMENT}}",
                "{{TOTAL_POSTS}}",
                "{{AVG_ENGAGEMENT_RATE}}",
            ):
                sections["general"].append(
                    self._placeholder_item(
                        "general",
                        placeholder_key,
                        mapping.get(placeholder_key),
                        overrides,
                    )
                )

            for platform, table_name in PLATFORM_TABLES.items():
                report = payload.get("reports", {}).get(platform) or {}
                row_id = report.get("id")
                if not row_id:
                    continue
                platform_trends = payload.get("trends", {}).get(platform, [])
                trend_db_fields = trend_database_fields(platform)
                current_trend_aliases: dict[str, list[str]] = {}
                for trend_index, trend in enumerate(
                    platform_trends,
                    start=1,
                ):
                    if str(trend.get("source_period_id")) != str(period_id):
                        continue
                    for trend_key, db_field in trend_db_fields.items():
                        current_trend_aliases.setdefault(
                            db_field,
                            [],
                        ).extend(
                            trend_placeholder_aliases(
                                platform,
                                trend_index,
                                trend_key,
                            )
                        )
                for field_name, label in PLATFORM_DATA_FIELDS[platform]:
                    value_type = REPORT_FIELD_TYPES.get(
                        field_name,
                        "number",
                    )
                    section = (
                        "demographics"
                        if field_name == "demographics"
                        else platform
                    )
                    sections[section].append(
                        self._field_item(
                            section=section,
                            table=table_name,
                            row_id=row_id,
                            field_name=field_name,
                            label=label,
                            value=report.get(field_name),
                            value_type=value_type,
                            platform=platform,
                            aliases=[
                                *placeholder_aliases(platform, field_name),
                                *current_trend_aliases.get(field_name, []),
                            ],
                            overrides=overrides,
                            override_scope=(
                                "derived"
                                if field_name in CALCULATED_REPORT_FIELDS
                                else "field"
                            ),
                        )
                    )
                for trend_index, trend in enumerate(
                    platform_trends,
                    start=1,
                ):
                    if (
                        not trend.get("report_id")
                        or str(trend.get("source_period_id"))
                        == str(period_id)
                    ):
                        continue
                    historical_fields: dict[str, dict] = {}
                    for trend_key, (trend_label, value_type) in TREND_FIELDS.items():
                        db_field = trend_db_fields[trend_key]
                        item = historical_fields.setdefault(
                            db_field,
                            {
                                "label": trend_label,
                                "value_type": value_type,
                                "value": trend.get(trend_key),
                                "aliases": [],
                            },
                        )
                        item["aliases"].extend(
                            trend_placeholder_aliases(
                                platform,
                                trend_index,
                                trend_key,
                            )
                        )
                    for db_field, trend_field in historical_fields.items():
                        sections[platform].append(
                            self._field_item(
                                section=platform,
                                table=table_name,
                                row_id=trend["report_id"],
                                field_name=db_field,
                                label=(
                                    f"{trend.get('period_label') or 'Historical'}"
                                    f" - {trend_field['label']}"
                                ),
                                value=trend_field["value"],
                                value_type=trend_field["value_type"],
                                platform=platform,
                                aliases=trend_field["aliases"],
                                overrides=overrides,
                                override_scope=(
                                    "derived"
                                    if db_field in CALCULATED_REPORT_FIELDS
                                    else "field"
                                ),
                                extra={
                                    "source_period_id": trend.get(
                                        "source_period_id"
                                    ),
                                    "historical": True,
                                    "warning": (
                                        "Editing this source period can affect "
                                        "other reports."
                                    ),
                                },
                            )
                        )

            for platform, rows in payload.get("kpi_results", {}).items():
                for row in rows:
                    for field_name, (label, value_type) in KPI_FIELDS.items():
                        sections["kpi"].append(
                            self._field_item(
                                section="kpi",
                                table="kpi_results",
                                row_id=row["id"],
                                field_name=field_name,
                                label=f"{platform.title()} {row['metric_name']} {label}",
                                value=row.get(field_name),
                                value_type=value_type,
                                platform=platform,
                                aliases=[],
                                overrides=overrides,
                                override_scope=(
                                    "derived"
                                    if field_name
                                    in {
                                        "actual_month",
                                        "actual_year",
                                        "achievement_month",
                                        "achievement_year",
                                    }
                                    else "field"
                                ),
                                extra={
                                    "metric_name": row["metric_name"],
                                },
                            )
                        )

            competitor_rows = conn.execute(
                text(
                    """
                    SELECT *
                    FROM competitor_profile_reports
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                    ORDER BY platform, total_engagement DESC NULLS LAST
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings()
            for row in competitor_rows:
                row = json_safe(dict(row))
                for field_name, (label, value_type) in COMPETITOR_FIELDS.items():
                    sections["competitor"].append(
                        self._field_item(
                            section="competitor",
                            table="competitor_profile_reports",
                            row_id=row["id"],
                            field_name=field_name,
                            label=f"{row['profile_name']} - {label}",
                            value=row.get(field_name),
                            value_type=value_type,
                            platform=row["platform"],
                            aliases=[],
                            overrides=overrides,
                            override_scope=(
                                "derived"
                                if field_name in CALCULATED_CONTENT_FIELDS
                                else "field"
                            ),
                            extra={
                                "profile_name": row["profile_name"],
                            },
                        )
                    )

            content_rows = conn.execute(
                text(
                    """
                    SELECT *
                    FROM social_content_reports
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                    ORDER BY platform, performance_bucket, content_rank,
                             published_at DESC NULLS LAST
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings()
            for row in content_rows:
                row = json_safe(dict(row))
                for field_name, (label, value_type) in CONTENT_FIELDS.items():
                    sections["content"].append(
                        self._field_item(
                            section="content",
                            table="social_content_reports",
                            row_id=row["id"],
                            field_name=field_name,
                            label=label,
                            value=row.get(field_name),
                            value_type=value_type,
                            platform=row["platform"],
                            aliases=[],
                            overrides=overrides,
                            override_scope=(
                                "derived"
                                if field_name in CALCULATED_CONTENT_FIELDS
                                else "field"
                            ),
                            extra={
                                "post_id": row.get("post_id"),
                                "caption": row.get("caption"),
                                "performance_bucket": row.get(
                                    "performance_bucket"
                                ),
                            },
                        )
                    )

            competitor_content_rows = conn.execute(
                text(
                    """
                    SELECT *
                    FROM competitor_content_reports
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                    ORDER BY platform, profile_name, content_rank,
                             published_at DESC NULLS LAST
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings()
            for row in competitor_content_rows:
                row = json_safe(dict(row))
                for field_name, (label, value_type) in CONTENT_FIELDS.items():
                    sections["content"].append(
                        self._field_item(
                            section="content",
                            table="competitor_content_reports",
                            row_id=row["id"],
                            field_name=field_name,
                            label=f"{row['profile_name']} - {label}",
                            value=row.get(field_name),
                            value_type=value_type,
                            platform=row["platform"],
                            aliases=[],
                            overrides=overrides,
                            extra={
                                "post_id": row.get("post_id"),
                                "caption": row.get("caption"),
                                "profile_name": row.get("profile_name"),
                                "performance_bucket": row.get(
                                    "performance_bucket"
                                ),
                            },
                        )
                    )

            for placeholder_key, value in sorted(mapping.items()):
                if is_ai_placeholder(placeholder_key):
                    continue
                section = (
                    "website_ads"
                    if placeholder_key.startswith(WEB_ADS_PREFIXES)
                    else "advanced"
                )
                sections[section].append(
                    self._placeholder_item(
                        section,
                        placeholder_key,
                        value,
                        overrides,
                    )
                )

            versions = {
                section: self._current_section_version(
                    conn,
                    period_id,
                    section,
                )
                for section in sections
            }
            return {
                "context": context,
                "sections": sections,
                "versions": versions,
                "history_count": conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM report_edit_history
                        WHERE report_period_id = :period_id
                        """
                    ),
                    {"period_id": period_id},
                ).scalar_one(),
            }

    def _current_section_version(
        self,
        conn,
        period_id: str,
        section: str,
    ) -> int:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0)
                    FROM report_overrides
                    WHERE report_period_id = :period_id
                      AND section_key = :section
                    """
                ),
                {"period_id": period_id, "section": section},
            ).scalar_one()
            or 0
        )

    def _upsert_override(
        self,
        conn,
        *,
        client_id: str,
        period_id: str,
        platform: str | None,
        scope: str,
        section: str,
        entity_type: str,
        entity_ref: str,
        override_key: str,
        value_type: str,
        source_value,
        override_value,
        actor: str,
        source_period_id: str | None = None,
    ) -> dict:
        row = conn.execute(
            text(
                """
                INSERT INTO report_overrides (
                    client_id, report_period_id, source_report_period_id,
                    platform, scope,
                    section_key, entity_type, entity_ref, override_key,
                    value_type, source_value, override_value, edited_by
                )
                VALUES (
                    :client_id, :period_id, :source_period_id,
                    :platform, :scope,
                    :section, :entity_type, :entity_ref, :override_key,
                    :value_type, CAST(:source_value AS JSONB),
                    CAST(:override_value AS JSONB), :actor
                )
                ON CONFLICT (
                    report_period_id, scope, entity_ref, override_key
                )
                DO UPDATE SET
                    platform = EXCLUDED.platform,
                    source_report_period_id =
                        EXCLUDED.source_report_period_id,
                    section_key = EXCLUDED.section_key,
                    value_type = EXCLUDED.value_type,
                    source_value = CASE
                        WHEN report_overrides.is_active
                        THEN report_overrides.source_value
                        ELSE EXCLUDED.source_value
                    END,
                    override_value = EXCLUDED.override_value,
                    edited_by = EXCLUDED.edited_by,
                    is_active = TRUE,
                    version = report_overrides.version + 1,
                    updated_at = now()
                RETURNING *
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "source_period_id": source_period_id or period_id,
                "platform": platform,
                "scope": scope,
                "section": section,
                "entity_type": entity_type,
                "entity_ref": entity_ref,
                "override_key": override_key,
                "value_type": value_type,
                "source_value": json_parameter(source_value),
                "override_value": json_parameter(override_value),
                "actor": actor,
            },
        ).mappings().one()
        return json_safe(dict(row))

    def _write_history(
        self,
        conn,
        override: dict,
        old_value,
        new_value,
        actor: str,
        action: str = "update",
    ):
        conn.execute(
            text(
                """
                INSERT INTO report_edit_history (
                    override_id, client_id, report_period_id, platform,
                    section_key, entity_type, entity_ref, field_key,
                    action, old_value, new_value, edited_by
                )
                VALUES (
                    :override_id, :client_id, :period_id, :platform,
                    :section, :entity_type, :entity_ref, :field_key,
                    :action, CAST(:old_value AS JSONB),
                    CAST(:new_value AS JSONB), :actor
                )
                """
            ),
            {
                "override_id": override["id"],
                "client_id": override["client_id"],
                "period_id": override["report_period_id"],
                "platform": override.get("platform"),
                "section": override["section_key"],
                "entity_type": override["entity_type"],
                "entity_ref": override["entity_ref"],
                "field_key": override["override_key"],
                "action": action,
                "old_value": json_parameter(old_value),
                "new_value": json_parameter(new_value),
                "actor": actor,
            },
        )

    def update_section(
        self,
        client_id: str,
        period_id: str,
        section: str,
        payload: dict,
    ) -> dict:
        actor = clean_actor(payload.get("actor"))
        changes = payload.get("changes")
        if not isinstance(changes, list) or not changes:
            raise ValueError("At least one change is required.")
        editor = self.get_editor(client_id, period_id)
        section_fields = {
            field["id"]: field
            for field in editor["sections"].get(section, [])
        }
        unknown = [
            change.get("id")
            for change in changes
            if change.get("id") not in section_fields
        ]
        if unknown:
            raise ValueError(
                f"Unknown or non-editable fields: {', '.join(map(str, unknown))}"
            )
        target_period_ids = {str(period_id)}
        for change in changes:
            field = section_fields[change["id"]]
            if field["kind"] != "placeholder":
                target_period_ids.add(
                    str(field.get("source_period_id") or period_id)
                )

        with self.engine.begin() as conn:
            self._context(conn, client_id, period_id)
            for target_period_id in sorted(target_period_ids):
                lock_report_period(conn, client_id, target_period_id)
            expected_version = int(payload.get("version") or 0)
            current_version = self._current_section_version(
                conn,
                period_id,
                section,
            )
            if expected_version != current_version:
                raise RuntimeError(
                    "VERSION_CONFLICT: report data changed after it was loaded."
                )

            updated = []
            rebuild_content = False
            recalculate_period_ids = {period_id}
            for change in changes:
                field = section_fields[change["id"]]
                new_value = parse_editor_value(
                    change.get("value"),
                    field["value_type"],
                )
                if field["kind"] == "placeholder":
                    placeholder_key = field["field_key"]
                    if is_ai_placeholder(placeholder_key):
                        raise ValueError("AI insight placeholders are read-only.")
                    override = self._upsert_override(
                        conn,
                        client_id=client_id,
                        period_id=period_id,
                        platform=None,
                        scope="placeholder",
                        section=section,
                        entity_type="report",
                        entity_ref="report",
                        override_key=placeholder_key,
                        value_type=field["value_type"],
                        source_value=field["source_value"],
                        override_value=new_value,
                        actor=actor,
                    )
                    self._write_history(
                        conn,
                        override,
                        field["value"],
                        new_value,
                        actor,
                    )
                    updated.append(override)
                    continue

                _kind, table_name, row_id, field_name = field["id"].split(
                    "|",
                    3,
                )
                if (
                    table_name not in ALLOWED_TABLE_FIELDS
                    or field_name not in ALLOWED_TABLE_FIELDS[table_name]
                ):
                    raise ValueError("Field is not editable.")
                target_period_id = (
                    field.get("source_period_id") or period_id
                )
                recalculate_period_ids.add(str(target_period_id))
                current_row = conn.execute(
                    text(
                        f"""
                        SELECT id, {field_name} AS current_value
                        FROM {table_name}
                        WHERE id = :row_id
                          AND client_id = :client_id
                          AND report_period_id = :target_period_id
                        FOR UPDATE
                        """
                    ),
                    {
                        "row_id": row_id,
                        "client_id": client_id,
                        "target_period_id": target_period_id,
                    },
                ).mappings().first()
                if not current_row:
                    raise ValueError("Editable data row was not found.")
                if field["value_type"] == "json":
                    assignment = f"{field_name} = CAST(:value AS JSONB)"
                    db_value = json_parameter(new_value)
                else:
                    assignment = f"{field_name} = :value"
                    db_value = new_value
                conn.execute(
                    text(
                        f"""
                        UPDATE {table_name}
                        SET {assignment}, updated_at = now()
                        WHERE id = :row_id
                          AND client_id = :client_id
                          AND report_period_id = :target_period_id
                        """
                    ),
                    {
                        "value": db_value,
                        "row_id": row_id,
                        "client_id": client_id,
                        "target_period_id": target_period_id,
                    },
                )
                self._apply_field_dependencies(
                    conn,
                    client_id,
                    str(target_period_id),
                    table_name,
                    row_id,
                    field_name,
                    current_row["current_value"],
                    new_value,
                )
                entity_ref = f"{table_name}:{row_id}"
                override = self._upsert_override(
                    conn,
                    client_id=client_id,
                    period_id=period_id,
                    platform=field.get("platform"),
                    scope=field.get("override_scope", "field"),
                    section=section,
                    entity_type=table_name,
                    entity_ref=entity_ref,
                    override_key=field_name,
                    value_type=field["value_type"],
                    source_value=field["source_value"],
                    override_value=new_value,
                    actor=actor,
                    source_period_id=target_period_id,
                )
                self._write_history(
                    conn,
                    override,
                    field["value"],
                    new_value,
                    actor,
                )
                updated.append(override)
                if (
                    table_name == "social_content_reports"
                    and field.get("performance_bucket") == "all"
                    and field_name
                    not in {"performance_bucket", "content_rank"}
                ):
                    rebuild_content = True

            for calculation_period_id in recalculate_period_ids:
                self._refresh_calculated_data(
                    conn,
                    client_id,
                    calculation_period_id,
                    rebuild_content=(
                        rebuild_content
                        and str(calculation_period_id) == str(period_id)
                    ),
                )
                reapply_field_overrides(
                    conn,
                    client_id,
                    calculation_period_id,
                    scopes={"derived"},
                )
            return {
                "updated": len(updated),
                "version": self._current_section_version(
                    conn,
                    period_id,
                    section,
                ),
            }

    def _canonical_platform_report(
        self,
        conn,
        client_id: str,
        period_id: str,
        platform: str,
    ):
        table_name = PLATFORM_TABLES[platform]
        return conn.execute(
            text(
                f"""
                SELECT *
                FROM {table_name}
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

    def _update_report_engagement_delta(
        self,
        conn,
        client_id: str,
        period_id: str,
        platform: str,
        engagement_delta: Decimal,
        component_field: str | None = None,
        component_delta: Decimal | None = None,
    ):
        table_name = PLATFORM_TABLES[platform]
        report = self._canonical_platform_report(
            conn,
            client_id,
            period_id,
            platform,
        )
        if not report:
            return
        old_total = decimal_value(report.get("total_engagement"))
        new_total = max(old_total + engagement_delta, Decimal("0"))
        audience_field = REPORT_AUDIENCE_FIELDS[table_name]
        new_rate = scaled_rate(
            report.get("engagement_rate"),
            old_total,
            new_total,
            report.get(audience_field),
        )
        assignments = [
            "total_engagement = :total_engagement",
            "engagement_rate = :engagement_rate",
            "updated_at = now()",
        ]
        params = {
            "report_id": report["id"],
            "total_engagement": new_total,
            "engagement_rate": new_rate,
        }
        if (
            component_field
            and component_delta is not None
            and component_field
            in REPORT_ENGAGEMENT_COMPONENTS.get(table_name, set())
        ):
            assignments.insert(
                0,
                f"{component_field} = GREATEST("
                f"COALESCE({component_field}, 0) + :component_delta, 0)",
            )
            params["component_delta"] = component_delta
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET {", ".join(assignments)}
                WHERE id = :report_id
                """
            ),
            params,
        )

    def _update_competitor_engagement_delta(
        self,
        conn,
        client_id: str,
        period_id: str,
        platform: str,
        profile_name: str | None,
        engagement_delta: Decimal,
    ):
        if not profile_name:
            return
        report = conn.execute(
            text(
                """
                SELECT id, total_engagement, engagement_rate,
                       total_followers
                FROM competitor_profile_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND platform = :platform
                  AND lower(profile_name) = lower(:profile_name)
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
                "profile_name": profile_name,
            },
        ).mappings().first()
        if not report:
            return
        old_total = decimal_value(report.get("total_engagement"))
        new_total = max(old_total + engagement_delta, Decimal("0"))
        new_rate = scaled_rate(
            report.get("engagement_rate"),
            old_total,
            new_total,
            report.get("total_followers"),
        )
        conn.execute(
            text(
                """
                UPDATE competitor_profile_reports
                SET total_engagement = :total_engagement,
                    engagement_rate = :engagement_rate,
                    updated_at = now()
                WHERE id = :report_id
                """
            ),
            {
                "report_id": report["id"],
                "total_engagement": new_total,
                "engagement_rate": new_rate,
            },
        )

    def _apply_report_dependencies(
        self,
        conn,
        table_name: str,
        row_id: str,
        field_name: str,
        old_value,
        new_value,
    ):
        report = conn.execute(
            text(f"SELECT * FROM {table_name} WHERE id = :row_id"),
            {"row_id": row_id},
        ).mappings().first()
        if not report:
            return
        audience_field = REPORT_AUDIENCE_FIELDS[table_name]
        old_numeric = decimal_value(old_value)
        new_numeric = decimal_value(new_value)

        if field_name in REPORT_ENGAGEMENT_COMPONENTS[table_name]:
            old_total = decimal_value(report.get("total_engagement"))
            new_total = max(
                old_total + (new_numeric - old_numeric),
                Decimal("0"),
            )
            new_rate = scaled_rate(
                report.get("engagement_rate"),
                old_total,
                new_total,
                report.get(audience_field),
            )
            conn.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET total_engagement = :total_engagement,
                        engagement_rate = :engagement_rate,
                        updated_at = now()
                    WHERE id = :row_id
                    """
                ),
                {
                    "row_id": row_id,
                    "total_engagement": new_total,
                    "engagement_rate": new_rate,
                },
            )
        elif field_name == "total_engagement":
            new_rate = scaled_rate(
                report.get("engagement_rate"),
                old_value,
                new_value,
                report.get(audience_field),
            )
            conn.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET engagement_rate = :engagement_rate,
                        updated_at = now()
                    WHERE id = :row_id
                    """
                ),
                {
                    "row_id": row_id,
                    "engagement_rate": new_rate,
                },
            )
        elif field_name == audience_field:
            current_rate = report.get("engagement_rate")
            old_audience = old_numeric
            new_audience = new_numeric
            if current_rate not in (None, "") and new_audience != 0:
                engagement_rate = (
                    decimal_value(current_rate)
                    * old_audience
                    / new_audience
                )
            elif new_audience != 0:
                engagement_rate = (
                    decimal_value(report.get("total_engagement"))
                    / new_audience
                    * Decimal("100")
                )
            else:
                engagement_rate = None
            conn.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET engagement_rate = :engagement_rate,
                        updated_at = now()
                    WHERE id = :row_id
                    """
                ),
                {
                    "row_id": row_id,
                    "engagement_rate": engagement_rate,
                },
            )

        growth_fields = REPORT_GROWTH_FIELDS[table_name]
        growth_field = growth_fields["growth"]
        rate_field = growth_fields["rate"]
        gained_field = growth_fields["gained"]
        lost_field = growth_fields["lost"]
        old_growth = decimal_value(report.get(growth_field))
        new_growth = old_growth
        if field_name == gained_field:
            new_growth = old_growth + (new_numeric - old_numeric)
        elif field_name == lost_field and gained_field:
            new_growth = old_growth - (new_numeric - old_numeric)
        elif field_name == growth_field:
            new_growth = new_numeric

        if (
            field_name in {gained_field, lost_field, growth_field}
            and not (
                field_name == lost_field
                and gained_field is None
            )
        ):
            previous_audience = (
                decimal_value(report.get(audience_field)) - new_growth
            )
            growth_rate = scaled_rate(
                report.get(rate_field),
                old_growth,
                new_growth,
                previous_audience,
            )
            conn.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET {growth_field} = :growth,
                        {rate_field} = :growth_rate,
                        updated_at = now()
                    WHERE id = :row_id
                    """
                ),
                {
                    "row_id": row_id,
                    "growth": new_growth,
                    "growth_rate": growth_rate,
                },
            )
        elif field_name == audience_field:
            previous_audience = new_numeric - old_growth
            growth_rate = (
                old_growth / previous_audience * Decimal("100")
                if previous_audience != 0
                else None
            )
            conn.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET {rate_field} = :growth_rate,
                        updated_at = now()
                    WHERE id = :row_id
                    """
                ),
                {
                    "row_id": row_id,
                    "growth_rate": growth_rate,
                },
            )

    def _apply_content_dependencies(
        self,
        conn,
        client_id: str,
        period_id: str,
        table_name: str,
        row_id: str,
        field_name: str,
        old_value,
        new_value,
    ):
        row = conn.execute(
            text(f"SELECT * FROM {table_name} WHERE id = :row_id"),
            {"row_id": row_id},
        ).mappings().first()
        if not row:
            return
        component_fields = {
            "likes",
            "comments",
            "shares",
            "saves",
            "reposts",
            "reactions",
        }
        engagement_delta = Decimal("0")
        component_delta = None
        if field_name in component_fields:
            component_delta = (
                decimal_value(new_value) - decimal_value(old_value)
            )
            engagement_delta = component_delta
            old_total = decimal_value(row.get("total_engagement"))
            new_total = max(old_total + engagement_delta, Decimal("0"))
        elif field_name == "total_engagement":
            old_total = decimal_value(old_value)
            new_total = decimal_value(new_value)
            engagement_delta = new_total - old_total
        else:
            return

        platform = row.get("platform")
        denominator = None
        if table_name == "social_content_reports":
            platform_report = self._canonical_platform_report(
                conn,
                client_id,
                period_id,
                platform,
            )
            if platform_report:
                denominator = platform_report.get(
                    REPORT_AUDIENCE_FIELDS[PLATFORM_TABLES[platform]]
                )
        else:
            competitor_report = conn.execute(
                text(
                    """
                    SELECT total_followers
                    FROM competitor_profile_reports
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                      AND platform = :platform
                      AND lower(profile_name) = lower(:profile_name)
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "client_id": client_id,
                    "period_id": period_id,
                    "platform": platform,
                    "profile_name": row.get("profile_name") or "",
                },
            ).scalar_one_or_none()
            denominator = competitor_report

        new_rate = scaled_rate(
            row.get("engagement_rate"),
            old_total,
            new_total,
            denominator,
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET total_engagement = :total_engagement,
                    engagement_rate = :engagement_rate,
                    updated_at = now()
                WHERE id = :row_id
                """
            ),
            {
                "row_id": row_id,
                "total_engagement": new_total,
                "engagement_rate": new_rate,
            },
        )

        if (
            table_name == "social_content_reports"
            and row.get("performance_bucket") == "all"
        ):
            self._update_report_engagement_delta(
                conn,
                client_id,
                period_id,
                platform,
                engagement_delta,
                field_name if component_delta is not None else None,
                component_delta,
            )
        elif table_name == "competitor_content_reports":
            self._update_competitor_engagement_delta(
                conn,
                client_id,
                period_id,
                platform,
                row.get("profile_name"),
                engagement_delta,
            )

    def _apply_field_dependencies(
        self,
        conn,
        client_id: str,
        period_id: str,
        table_name: str,
        row_id: str,
        field_name: str,
        old_value,
        new_value,
    ):
        if table_name in REPORT_ENGAGEMENT_COMPONENTS:
            self._apply_report_dependencies(
                conn,
                table_name,
                row_id,
                field_name,
                old_value,
                new_value,
            )
        elif table_name in {
            "social_content_reports",
            "competitor_content_reports",
        }:
            self._apply_content_dependencies(
                conn,
                client_id,
                period_id,
                table_name,
                row_id,
                field_name,
                old_value,
                new_value,
            )

    def _refresh_content_rankings(
        self,
        conn,
        client_id: str,
        period_id: str,
    ):
        content_columns = """
            client_id, profile_id, report_period_id, platform, source,
            post_id, published_at, caption, permalink, image_url,
            content_type, content_rank, performance_bucket,
            likes, comments, shares, saves, reposts, reactions,
            views, reach, profile_visits, total_engagement, engagement_rate,
            audience_demographics, raw_metrics
        """
        params = {"client_id": client_id, "period_id": period_id}
        conn.execute(
            text(
                """
                DELETE FROM social_content_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND performance_bucket IN ('top', 'low')
                """
            ),
            params,
        )
        conn.execute(
            text(
                f"""
                INSERT INTO social_content_reports ({content_columns})
                SELECT
                    client_id, profile_id, report_period_id, platform, source,
                    post_id, published_at, caption, permalink, image_url,
                    content_type, ranking, 'top',
                    likes, comments, shares, saves, reposts, reactions,
                    views, reach, profile_visits, total_engagement, engagement_rate,
                    audience_demographics, raw_metrics
                FROM (
                    SELECT source_rows.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY platform
                               ORDER BY total_engagement DESC NULLS LAST,
                                        published_at DESC NULLS LAST,
                                        id
                           ) AS ranking
                    FROM social_content_reports source_rows
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                      AND performance_bucket = 'all'
                      AND COALESCE(content_type, '') <> 'story'
                ) ranked
                WHERE ranking <= 3
                """
            ),
            params,
        )
        conn.execute(
            text(
                f"""
                INSERT INTO social_content_reports ({content_columns})
                SELECT
                    client_id, profile_id, report_period_id, platform, source,
                    post_id, published_at, caption, permalink, image_url,
                    content_type, low_ranking, 'low',
                    likes, comments, shares, saves, reposts, reactions,
                    views, reach, profile_visits, total_engagement, engagement_rate,
                    audience_demographics, raw_metrics
                FROM (
                    SELECT source_rows.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY platform
                               ORDER BY total_engagement ASC NULLS LAST,
                                        published_at ASC NULLS LAST,
                                        id
                           ) AS low_ranking
                    FROM social_content_reports source_rows
                    WHERE client_id = :client_id
                      AND report_period_id = :period_id
                      AND performance_bucket = 'all'
                      AND COALESCE(content_type, '') <> 'story'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM social_content_reports top_rows
                          WHERE top_rows.client_id = source_rows.client_id
                            AND top_rows.report_period_id =
                                source_rows.report_period_id
                            AND top_rows.platform = source_rows.platform
                            AND top_rows.performance_bucket = 'top'
                            AND top_rows.post_id IS NOT DISTINCT FROM
                                source_rows.post_id
                      )
                ) ranked
                WHERE low_ranking <= 3
                """
            ),
            params,
        )

    def _refresh_calculated_data(
        self,
        conn,
        client_id: str,
        period_id: str,
        rebuild_content: bool = False,
    ):
        if rebuild_content:
            self._refresh_content_rankings(conn, client_id, period_id)
        metric_sources = {
            "instagram": {
                "followers": ("instagram_reports", "follower_growth", True),
                "engagement": ("instagram_reports", "total_engagement", True),
                "reach": ("instagram_reports", "reach", True),
            },
            "facebook": {
                "followers": ("facebook_reports", "follower_growth", True),
                "engagement": ("facebook_reports", "total_engagement", True),
                "reach": ("facebook_reports", "reach", True),
            },
            "tiktok": {
                "followers": ("tiktok_reports", "follower_growth", True),
                "likes": ("tiktok_reports", "likes", True),
                "views": ("tiktok_reports", "total_views", True),
            },
            "youtube": {
                "subscribers": ("youtube_reports", "subscriber_growth", True),
                "engagement": ("youtube_reports", "total_engagement", True),
                "views": ("youtube_reports", "total_views", True),
            },
            "linkedin": {
                "followers": ("linkedin_reports", "follower_growth", True),
                "engagement": ("linkedin_reports", "total_engagement", True),
                "impressions": ("linkedin_reports", "impressions", True),
            },
            "threads": {
                "followers": ("threads_reports", "follower_growth", True),
                "engagement": ("threads_reports", "total_engagement", True),
                "views": ("threads_reports", "total_views", True),
            },
        }
        selected_period = conn.execute(
            text(
                "SELECT period_start FROM report_periods WHERE id = :period_id"
            ),
            {"period_id": period_id},
        ).scalar_one()
        for platform, metrics in metric_sources.items():
            for metric_name, (table_name, column_name, cumulative) in metrics.items():
                actual_month = conn.execute(
                    text(
                        f"""
                        SELECT {column_name}
                        FROM {table_name}
                        WHERE client_id = :client_id
                          AND report_period_id = :period_id
                        ORDER BY
                            (profile_id IS NOT NULL) DESC,
                            updated_at DESC,
                            created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"client_id": client_id, "period_id": period_id},
                ).scalar_one_or_none()
                if cumulative:
                    actual_year = conn.execute(
                        text(
                            f"""
                            SELECT SUM(selected.metric_value)
                            FROM (
                                SELECT DISTINCT ON (r.report_period_id)
                                    r.report_period_id,
                                    r.{column_name} AS metric_value
                                FROM {table_name} r
                                JOIN report_periods rp
                                  ON rp.id = r.report_period_id
                                WHERE r.client_id = :client_id
                                  AND EXTRACT(YEAR FROM rp.period_start) = :year
                                  AND rp.period_start <= :period_start
                                ORDER BY
                                    r.report_period_id,
                                    (r.profile_id IS NOT NULL) DESC,
                                    r.updated_at DESC,
                                    r.created_at DESC
                            ) selected
                            """
                        ),
                        {
                            "client_id": client_id,
                            "year": selected_period.year,
                            "period_start": selected_period,
                        },
                    ).scalar_one_or_none()
                else:
                    actual_year = actual_month
                conn.execute(
                    text(
                        """
                        UPDATE kpi_results
                        SET actual_month = CAST(:actual_month AS NUMERIC),
                            actual_year = CAST(:actual_year AS NUMERIC),
                            achievement_month = CASE
                                WHEN target_month IS NOT NULL
                                 AND target_month <> 0
                                 AND CAST(:actual_month AS NUMERIC) IS NOT NULL
                                THEN ROUND((
                                    CAST(:actual_month AS NUMERIC)
                                    / target_month
                                ) * 100, 2)
                                ELSE NULL
                            END,
                            achievement_year = CASE
                                WHEN target_year IS NOT NULL
                                 AND target_year <> 0
                                 AND CAST(:actual_year AS NUMERIC) IS NOT NULL
                                THEN ROUND((
                                    CAST(:actual_year AS NUMERIC)
                                    / target_year
                                ) * 100, 2)
                                ELSE NULL
                            END,
                            updated_at = now()
                        WHERE client_id = :client_id
                          AND report_period_id = :period_id
                          AND platform = :platform
                          AND metric_name = :metric_name
                        """
                    ),
                    {
                        "actual_month": actual_month,
                        "actual_year": actual_year,
                        "client_id": client_id,
                        "period_id": period_id,
                        "platform": platform,
                        "metric_name": metric_name,
                    },
                )

    def restore_override(
        self,
        client_id: str,
        period_id: str,
        override_id: str,
        actor_value,
    ) -> dict:
        actor = clean_actor(actor_value)
        with self.engine.begin() as conn:
            self._context(conn, client_id, period_id)
            candidate = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_overrides
                    WHERE id = :override_id
                      AND client_id = :client_id
                      AND report_period_id = :period_id
                      AND is_active = TRUE
                    """
                ),
                {
                    "override_id": override_id,
                    "client_id": client_id,
                    "period_id": period_id,
                },
            ).mappings().first()
            if not candidate:
                raise ValueError("Active override not found.")
            target_period_ids = {str(period_id)}
            if candidate["scope"] in {"field", "derived"}:
                target_period_ids.add(
                    str(
                        candidate.get("source_report_period_id")
                        or period_id
                    )
                )
            for target_period_id in sorted(target_period_ids):
                lock_report_period(conn, client_id, target_period_id)
            override = conn.execute(
                text(
                    """
                    SELECT *
                    FROM report_overrides
                    WHERE id = :override_id
                      AND client_id = :client_id
                      AND report_period_id = :period_id
                      AND is_active = TRUE
                    FOR UPDATE
                    """
                ),
                {
                    "override_id": override_id,
                    "client_id": client_id,
                    "period_id": period_id,
                },
            ).mappings().first()
            if not override:
                raise ValueError("Active override not found.")
            override = json_safe(dict(override))
            rebuild_content = False
            if override["scope"] in {"field", "derived"}:
                table_name, row_id = override["entity_ref"].split(":", 1)
                field_name = override["override_key"]
                target_period_id = (
                    override.get("source_report_period_id") or period_id
                )
                if (
                    table_name not in ALLOWED_TABLE_FIELDS
                    or field_name not in ALLOWED_TABLE_FIELDS[table_name]
                ):
                    raise ValueError("Override target is not editable.")
                value = override.get("source_value")
                if override["value_type"] == "json":
                    assignment = f"{field_name} = CAST(:value AS JSONB)"
                    value = json_parameter(value)
                else:
                    assignment = f"{field_name} = :value"
                conn.execute(
                    text(
                        f"""
                        UPDATE {table_name}
                        SET {assignment}, updated_at = now()
                        WHERE id = :row_id
                          AND client_id = :client_id
                          AND report_period_id = :target_period_id
                        """
                    ),
                    {
                        "value": value,
                        "row_id": row_id,
                        "client_id": client_id,
                        "target_period_id": target_period_id,
                    },
                )
                self._apply_field_dependencies(
                    conn,
                    client_id,
                    str(target_period_id),
                    table_name,
                    row_id,
                    field_name,
                    override.get("override_value"),
                    override.get("source_value"),
                )
                if table_name == "social_content_reports":
                    bucket = conn.execute(
                        text(
                            """
                            SELECT performance_bucket
                            FROM social_content_reports
                            WHERE id = :row_id
                            """
                        ),
                        {"row_id": row_id},
                    ).scalar_one_or_none()
                    rebuild_content = bucket == "all"
            conn.execute(
                text(
                    """
                    UPDATE report_overrides
                    SET is_active = FALSE,
                        version = version + 1,
                        edited_by = :actor,
                        updated_at = now()
                    WHERE id = :override_id
                    """
                ),
                {"actor": actor, "override_id": override_id},
            )
            self._write_history(
                conn,
                override,
                override.get("override_value"),
                override.get("source_value"),
                actor,
                action="restore",
            )
            calculation_periods = {str(period_id)}
            if override["scope"] in {"field", "derived"}:
                calculation_periods.add(
                    str(
                        override.get("source_report_period_id")
                        or period_id
                    )
                )
            for calculation_period_id in calculation_periods:
                self._refresh_calculated_data(
                    conn,
                    client_id,
                    calculation_period_id,
                    rebuild_content=(
                        rebuild_content
                        and calculation_period_id == str(period_id)
                    ),
                )
                reapply_field_overrides(
                    conn,
                    client_id,
                    calculation_period_id,
                    scopes={"derived"},
                )
            return {"restored": True, "override_id": override_id}

    def history(self, client_id: str, period_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            self._context(conn, client_id, period_id)
            return [
                json_safe(dict(row))
                for row in conn.execute(
                    text(
                        """
                        SELECT *
                        FROM report_edit_history
                        WHERE client_id = :client_id
                          AND report_period_id = :period_id
                        ORDER BY created_at DESC
                        LIMIT 500
                        """
                    ),
                    {"client_id": client_id, "period_id": period_id},
                ).mappings()
            ]

    def upload_asset(
        self,
        client_id: str,
        period_id: str,
        actor_value,
        filename: str,
        content_type: str,
        content: bytes,
        platform: str | None = None,
    ) -> dict:
        actor = clean_actor(actor_value)
        if not content or len(content) > 6_000_000:
            raise ValueError("Image must be between 1 byte and 6 MB.")
        allowed_types = {"image/png", "image/jpeg", "image/webp"}
        guessed_type = content_type or mimetypes.guess_type(filename)[0]
        if guessed_type not in allowed_types:
            raise ValueError("Only PNG, JPEG, and WebP images are supported.")
        bucket_name = str(os.getenv("GCS_REPORT_ASSET_BUCKET") or "").strip()
        if not bucket_name:
            raise RuntimeError("GCS_REPORT_ASSET_BUCKET is not configured.")
        with self.engine.begin() as conn:
            self._context(conn, client_id, period_id)
            lock_report_period(conn, client_id, period_id)
        safe_name = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            Path(filename or "asset").name,
        ).strip("-")
        object_name = (
            f"report-assets/{client_id}/{period_id}/{uuid4()}-{safe_name}"
        )
        from google.cloud import storage

        client = storage.Client()
        blob = client.bucket(bucket_name).blob(object_name)
        blob.upload_from_string(content, content_type=guessed_type)
        public_url = (
            f"https://storage.googleapis.com/{bucket_name}/{object_name}"
        )
        try:
            with self.engine.begin() as conn:
                self._context(conn, client_id, period_id)
                lock_report_period(conn, client_id, period_id)
                row = conn.execute(
                    text(
                        """
                        INSERT INTO report_assets (
                            client_id, report_period_id, platform, object_name,
                            original_name, content_type, size_bytes, public_url,
                            uploaded_by
                        )
                        VALUES (
                            :client_id, :period_id, :platform, :object_name,
                            :original_name, :content_type, :size_bytes,
                            :public_url, :actor
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "client_id": client_id,
                        "period_id": period_id,
                        "platform": platform,
                        "object_name": object_name,
                        "original_name": filename,
                        "content_type": guessed_type,
                        "size_bytes": len(content),
                        "public_url": public_url,
                        "actor": actor,
                    },
                ).mappings().one()
        except Exception:
            try:
                blob.delete()
            except Exception:
                pass
            raise
        return json_safe(dict(row))


def active_placeholder_overrides(
    engine,
    client_id: str,
    period_id: str,
) -> dict[str, object]:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT override_key, override_value
                FROM report_overrides
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND scope = 'placeholder'
                  AND is_active = TRUE
                """
            ),
            {"client_id": client_id, "period_id": period_id},
        ).mappings()
        return {
            row["override_key"]: row["override_value"]
            for row in rows
            if not is_ai_placeholder(row["override_key"])
        }


def reapply_field_overrides(
    conn,
    client_id: str,
    period_id: str,
    scopes: set[str] | None = None,
):
    dependency_service = ReportEditorService.__new__(ReportEditorService)
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM report_overrides
            WHERE client_id = :client_id
              AND COALESCE(
                    source_report_period_id,
                    report_period_id
                  ) = :period_id
              AND scope IN ('field', 'derived')
              AND is_active = TRUE
            """
        ),
        {"client_id": client_id, "period_id": period_id},
    ).mappings()
    for row in rows:
        if scopes is not None and row["scope"] not in scopes:
            continue
        table_name, row_id = row["entity_ref"].split(":", 1)
        field_name = row["override_key"]
        if (
            table_name not in ALLOWED_TABLE_FIELDS
            or field_name not in ALLOWED_TABLE_FIELDS[table_name]
        ):
            continue
        source_row = conn.execute(
            text(
                f"""
                SELECT id, {field_name} AS source_value
                FROM {table_name}
                WHERE id = :row_id
                  AND client_id = :client_id
                  AND report_period_id = :period_id
                """
            ),
            {
                "row_id": row_id,
                "client_id": client_id,
                "period_id": period_id,
            },
        ).mappings().first()
        if not source_row:
            continue
        source_value = source_row["source_value"]
        if row["value_type"] == "json":
            assignment = f"{field_name} = CAST(:value AS JSONB)"
            override_value = json_parameter(row["override_value"])
        else:
            assignment = f"{field_name} = :value"
            override_value = row["override_value"]
        conn.execute(
            text(
                """
                UPDATE report_overrides
                SET source_value = CAST(:source_value AS JSONB),
                    source_updated_at = now(),
                    updated_at = now()
                WHERE id = :override_id
                """
            ),
            {
                "source_value": json_parameter(source_value),
                "override_id": row["id"],
            },
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET {assignment}, updated_at = now()
                WHERE id = :row_id
                  AND client_id = :client_id
                  AND report_period_id = :period_id
                """
            ),
            {
                "value": override_value,
                "row_id": row_id,
                "client_id": client_id,
                "period_id": period_id,
            },
        )
        dependency_service._apply_field_dependencies(
            conn,
            client_id,
            str(period_id),
            table_name,
            row_id,
            field_name,
            source_value,
            row["override_value"],
        )
