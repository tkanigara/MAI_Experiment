from __future__ import annotations

import calendar
import cgi
import csv
import io
import json
import os
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = Path(__file__).resolve().parent
STATIC_DIR = DASHBOARD_DIR / "dist"
if not STATIC_DIR.exists():
    STATIC_DIR = DASHBOARD_DIR / "static"
PLATFORM_TABLES = {
    "instagram": "instagram_reports",
    "facebook": "facebook_reports",
    "tiktok": "tiktok_reports",
    "youtube": "youtube_reports",
}
PLATFORM_KPI_METRICS = {
    "instagram": {"followers", "engagement", "reach"},
    "facebook": {"followers", "engagement", "reach"},
    "tiktok": {"followers", "engagement", "views"},
    "youtube": {"subscribers", "engagement", "views"},
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
    "ig_post": {
        "label": "Instagram Posts",
        "platform": "instagram",
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
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Reach per post", "Engagement"],
    },
    "tt_post": {
        "label": "TikTok Posts",
        "platform": "tiktok",
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Impressions/views per post", "Engagement"],
    },
    "yt_post": {
        "label": "YouTube Posts",
        "platform": "youtube",
        "required_columns": ["Date", "Profile", "Message", "Number of Likes", "Number of comments", "Post-ID", "Link", "Image Link"],
        "important_columns": ["Reactions, Comments & Shares", "Impressions/views per post", "Engagement"],
    },
}
SOCIAL_NETWORK_PLATFORMS = {
    "INSTAGRAM": "instagram",
    "FACEBOOK": "facebook",
    "TIKTOK": "tiktok",
    "YOUTUBE": "youtube",
}


def database_url() -> str:
    load_dotenv(BASE_DIR / ".env")
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://mai_user:mai_password@localhost:55432/mai_socmed_report",
    )


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


def numeric(row: dict, key: str, default=0):
    value = parse_number(row.get(key))
    return default if value is None else value


def engagement_percent(value):
    number = parse_number(value)
    if number is None:
        return None
    return round(number * 100, 2) if abs(number) <= 1 else round(number, 2)


def parse_post_date(value):
    if not value:
        return None
    for fmt in ("%d/%m/%Y, %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
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


def post_json(row: dict, content_type: str):
    total_engagement = parse_number(row.get("Reactions, Comments & Shares"))
    if total_engagement is None:
        total_engagement = numeric(row, "Number of Likes") + numeric(row, "Number of comments") + numeric(row, "Story shares")
    return {
        "post_id": row.get("Post-ID"),
        "published_at": json_safe(parse_post_date(row.get("Date"))),
        "caption": row.get("Message") or "-",
        "permalink": row.get("Link"),
        "image_url": row.get("Image Link"),
        "content_type": content_type,
        "likes": numeric(row, "Number of Likes"),
        "comments": numeric(row, "Number of comments"),
        "shares": numeric(row, "Story shares"),
        "views": parse_number(row.get("Impressions/views per post") or row.get("Story views")),
        "reach": parse_number(row.get("Reach per post") or row.get("Story reach")),
        "total_engagement": total_engagement,
        "engagement_rate": engagement_percent(row.get("Engagement") or row.get("Post interaction rate")),
    }


def summarize_posts(rows: list[dict], content_type: str):
    summary_rows = [row for row in rows if str(row.get("Post-ID", "")).strip().upper() == "SUMME"]
    content_rows = [row for row in rows if str(row.get("Post-ID", "")).strip().upper() != "SUMME"]
    posts = [post_json(row, content_type) for row in content_rows]
    posts.sort(key=lambda item: item.get("total_engagement") or 0, reverse=True)
    low_posts = sorted(posts, key=lambda item: item.get("total_engagement") or 0)
    if summary_rows:
        summary_post = post_json(summary_rows[0], content_type)
        totals = {
            "likes": summary_post.get("likes") or 0,
            "comments": summary_post.get("comments") or 0,
            "shares": summary_post.get("shares") or 0,
            "reach": summary_post.get("reach") or 0,
            "views": summary_post.get("views") or 0,
            "engagement": summary_post.get("total_engagement") or 0,
            "count": len(posts),
        }
    else:
        totals = {
            "likes": sum((item.get("likes") or 0) for item in posts),
            "comments": sum((item.get("comments") or 0) for item in posts),
            "shares": sum((item.get("shares") or 0) for item in posts),
            "reach": sum((item.get("reach") or 0) for item in posts),
            "views": sum((item.get("views") or 0) for item in posts),
            "engagement": sum((item.get("total_engagement") or 0) for item in posts),
            "count": len(posts),
        }
    return {"top_posts": posts[:5], "low_posts": low_posts[:5], "totals": totals, "raw_posts": posts}


class DashboardRepository:
    def __init__(self):
        self.engine = create_engine(database_url(), pool_pre_ping=True)

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
        required = ["client_code", "client_name"]
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")
        client_code = str(payload["client_code"]).strip().lower().replace(" ", "-")
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO clients (
                        client_code, client_name, industry,
                        has_instagram, has_facebook, has_tiktok, has_youtube
                    )
                    VALUES (
                        :client_code, :client_name, :industry,
                        :has_instagram, :has_facebook, :has_tiktok, :has_youtube
                    )
                    RETURNING id, client_code, client_name, industry,
                              has_instagram, has_facebook, has_tiktok, has_youtube,
                              0 AS connected_profiles
                    """
                ),
                {
                    "client_code": client_code,
                    "client_name": str(payload["client_name"]).strip(),
                    "industry": payload.get("industry") or None,
                    "has_instagram": bool(payload.get("has_instagram")),
                    "has_facebook": bool(payload.get("has_facebook")),
                    "has_tiktok": bool(payload.get("has_tiktok")),
                    "has_youtube": bool(payload.get("has_youtube")),
                },
            ).mappings().one()
            return row_dict(row)

    def delete_client(self, client_id: str):
        with self.engine.begin() as conn:
            client = conn.execute(
                text("SELECT id, client_name FROM clients WHERE id = :client_id"),
                {"client_id": client_id},
            ).mappings().first()
            if not client:
                raise ValueError("Client not found")
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

    def platforms(self, client_id: str):
        with self.engine.begin() as conn:
            client = conn.execute(
                text(
                    """
                    SELECT id, client_code, client_name, industry,
                           has_instagram, has_facebook, has_tiktok, has_youtube
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
                    COUNT(DISTINCT rar.endpoint) FILTER (
                        WHERE rar.endpoint LIKE 'csv_import/%'
                    ) AS uploaded_files,
                    (
                        SELECT COUNT(*) FROM instagram_reports r
                        WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                    ) + (
                        SELECT COUNT(*) FROM facebook_reports r
                        WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                    ) + (
                        SELECT COUNT(*) FROM tiktok_reports r
                        WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                    ) + (
                        SELECT COUNT(*) FROM youtube_reports r
                        WHERE r.client_id = rp.client_id AND r.report_period_id = rp.id
                    ) AS platform_reports
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
            status = f"{uploaded_files} of 7 files uploaded" if uploaded_files else f"{platform_reports} platform reports"
            months.append(
                {
                    "id": row["id"],
                    "label": row["period_label"] or row["period_start"].strftime("%B %Y"),
                    "slug": month_slug_from_date(row["period_start"]),
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "uploaded_files": uploaded_files,
                    "platform_reports": platform_reports,
                    "status": status,
                    "state": "ready" if platform_reports else "partial",
                }
            )
        return json_safe(months)

    def overview(self, client_id: str, platform: str):
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
                    ORDER BY rp.period_end DESC
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            report_data = row_dict(report)
            period_id = report_data["report_period_id"] if report_data else None
            kpi_results = []
            competitor_profiles = []
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
            kpi_targets = [
                row_dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT id, metric_name, period_year, target_month,
                               target_year, unit, notes, updated_at
                        FROM kpi_targets
                        WHERE client_id = :client_id AND platform = :platform
                        ORDER BY period_year DESC, metric_name
                        """
                    ),
                    {"client_id": client_id, "platform": platform},
                ).mappings()
            ]
        if report_data is not None:
            report_data["competitor_profiles"] = competitor_profiles
        return {
            "platform": platform,
            "report": report_data,
            "metrics": overview_metrics(platform, report_data),
            "kpi_results": kpi_results,
            "kpi_targets": kpi_targets,
            "competitor_profiles": competitor_profiles,
            "top_posts": (report_data or {}).get("top_posts") or [],
            "low_posts": (report_data or {}).get("low_posts") or [],
        }

    def upsert_kpi_target(self, payload: dict):
        required = ["client_id", "platform", "metric_name", "period_year"]
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
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO kpi_targets (
                        client_id, platform, metric_name, period_year,
                        target_month, target_year, unit, notes, created_by
                    )
                    VALUES (
                        :client_id, :platform, :metric_name, :period_year,
                        :target_month, :target_year, :unit, :notes, :created_by
                    )
                    ON CONFLICT (client_id, platform, metric_name, period_year)
                    DO UPDATE SET
                        target_month = EXCLUDED.target_month,
                        target_year = EXCLUDED.target_year,
                        unit = EXCLUDED.unit,
                        notes = EXCLUDED.notes,
                        updated_at = now()
                    RETURNING id, metric_name, period_year, target_month,
                              target_year, unit, notes, updated_at
                    """
                ),
                {
                    "client_id": payload["client_id"],
                    "platform": platform,
                    "metric_name": metric_name,
                    "period_year": int(payload["period_year"]),
                    "target_month": payload.get("target_month") or None,
                    "target_year": payload.get("target_year") or None,
                    "unit": payload.get("unit") or None,
                    "notes": payload.get("notes") or None,
                    "created_by": payload.get("created_by") or "dashboard",
                },
            ).mappings().one()
            synced = self.sync_kpi_results(conn, payload, row["id"], metric_name)
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
                """
            ),
            {
                "target_id": target_id,
                "client_id": payload["client_id"],
                "platform": payload["platform"],
                "metric_name": metric_name,
                "period_year": int(payload["period_year"]),
                "target_month": payload.get("target_month") or None,
                "target_year": payload.get("target_year") or None,
                "unit": payload.get("unit") or None,
            },
        )
        return result.rowcount

    def import_csv_report(self, payload: dict, files: dict):
        client_id = payload.get("client_id")
        month_slug = payload.get("month_slug") or "june-2026"
        if not client_id:
            raise ValueError("Missing client_id")
        period_start, period_end, period_label = month_range_from_slug(month_slug)
        file_results = []
        parsed_files = {}
        missing_files = []
        for slot, spec in CSV_IMPORT_SLOTS.items():
            file_item = files.get(slot)
            if file_item is None or not getattr(file_item, "filename", ""):
                missing_files.append(spec["label"])
                file_results.append(
                    {
                        "slot": slot,
                        "label": spec["label"],
                        "filename": None,
                        "rows": 0,
                        "warnings": ["File was not uploaded."],
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
            period_id = self.ensure_report_period(conn, client_id, period_start, period_end, period_label)
            run_id = self.create_import_run(conn, client_id, period_id, parsed_files, missing_files)
            profile_ids = self.upsert_account_profiles(conn, client_id, parsed_files.get("account", {}).get("rows", []))
            self.store_raw_csv_rows(conn, run_id, client_id, profile_ids, parsed_files)
            post_summaries = {
                "instagram": self.combine_post_summaries(
                    summarize_posts(parsed_files.get("ig_post", {}).get("rows", []), "post"),
                    summarize_posts(parsed_files.get("ig_story", {}).get("rows", []), "story"),
                ),
                "facebook": summarize_posts(parsed_files.get("fb_post", {}).get("rows", []), "post"),
                "tiktok": summarize_posts(parsed_files.get("tt_post", {}).get("rows", []), "video"),
                "youtube": summarize_posts(parsed_files.get("yt_post", {}).get("rows", []), "video"),
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
            kpi_count = self.upsert_kpi_results_from_reports(conn, client_id, period_id, reports)
            conn.execute(
                text("UPDATE etl_runs SET finished_at = now(), status = 'success' WHERE id = :run_id"),
                {"run_id": run_id},
            )

        warnings = sum(len(item.get("warnings") or []) for item in file_results)
        return {
            "period": {"id": period_id, "label": period_label, "start": period_start, "end": period_end},
            "summary": {
                "uploaded": len(parsed_files),
                "expected": len(CSV_IMPORT_SLOTS),
                "missing_files": missing_files,
                "warnings": warnings,
                "platform_reports": reports,
                "competitor_rows": competitor_count,
                "kpi_results": kpi_count,
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
        profile_ids = {}
        flags = {"instagram": False, "facebook": False, "tiktok": False, "youtube": False}
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
                    updated_at = now()
                WHERE id = :client_id
                """
            ),
            {"client_id": client_id, **flags},
        )
        return profile_ids

    def store_raw_csv_rows(self, conn, run_id, client_id, profile_ids, parsed_files):
        for slot, data in parsed_files.items():
            platform = CSV_IMPORT_SLOTS[slot]["platform"]
            endpoint = f"csv_import/{slot}"
            for row in data["rows"]:
                row_platform = platform or platform_from_row(row)
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
        combined = {
            "top_posts": post_summary["top_posts"],
            "low_posts": post_summary["low_posts"],
            "raw_posts": post_summary["raw_posts"] + story_summary["raw_posts"],
            "totals": {},
            "story_count": story_summary["totals"]["count"],
        }
        for key in ("likes", "comments", "shares", "reach", "views", "engagement", "count"):
            combined["totals"][key] = post_summary["totals"].get(key, 0) + story_summary["totals"].get(key, 0)
        return combined

    def upsert_platform_reports(self, conn, client_id, period_id, profile_ids, account_rows, post_summaries, parsed_files):
        account_by_platform = {platform_from_row(row): row for row in account_rows if platform_from_row(row)}
        reports = {}
        for platform, table in PLATFORM_TABLES.items():
            account = account_by_platform.get(platform)
            if not account and not post_summaries.get(platform, {}).get("totals", {}).get("count"):
                continue
            summary = post_summaries.get(platform, {"totals": {}, "top_posts": [], "low_posts": []})
            totals = summary.get("totals", {})
            total_engagement = totals.get("engagement") or numeric(account or {}, "Number of Likes") + numeric(account or {}, "Number of comments")
            base = {
                "client_id": client_id,
                "profile_id": profile_ids.get(platform),
                "period_id": period_id,
                "followers": parse_number((account or {}).get("Follower")),
                "posts": parse_number((account or {}).get("Number of posts")) or totals.get("count"),
                "engagement_rate": engagement_percent((account or {}).get("Engagement")),
                "likes": numeric(account or {}, "Number of Likes") or totals.get("likes"),
                "comments": numeric(account or {}, "Number of comments") or totals.get("comments"),
                "shares": totals.get("shares"),
                "reach": totals.get("reach"),
                "views": totals.get("views"),
                "engagement": total_engagement,
                "story_posts": summary.get("story_count", 0),
                "top_posts": json.dumps(summary.get("top_posts") or []),
                "low_posts": json.dumps(summary.get("low_posts") or []),
                "raw_sections": json.dumps(
                    {
                        "account": account,
                        "post_rows": len(summary.get("raw_posts") or []),
                        "files": {slot: data["filename"] for slot, data in parsed_files.items()},
                    }
                ),
            }
            if platform == "youtube":
                report_id = self.upsert_youtube_report(conn, table, base)
            elif platform == "tiktok":
                report_id = self.upsert_tiktok_report(conn, table, base)
            else:
                report_id = self.upsert_meta_report(conn, table, base)
            reports[platform] = {"report_id": report_id, **base}
        return reports

    def upsert_meta_report(self, conn, table, data):
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_followers, reach, impressions, total_engagement,
                    engagement_rate, likes, comments, shares, total_posts,
                    story_posts, top_posts, low_posts, raw_sections
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :reach, :views, :engagement,
                    :engagement_rate, :likes, :comments, :shares, :posts,
                    :story_posts, CAST(:top_posts AS JSONB), CAST(:low_posts AS JSONB),
                    CAST(:raw_sections AS JSONB)
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_followers = EXCLUDED.total_followers,
                    reach = EXCLUDED.reach,
                    impressions = EXCLUDED.impressions,
                    total_engagement = EXCLUDED.total_engagement,
                    engagement_rate = EXCLUDED.engagement_rate,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    shares = EXCLUDED.shares,
                    total_posts = EXCLUDED.total_posts,
                    story_posts = EXCLUDED.story_posts,
                    top_posts = EXCLUDED.top_posts,
                    low_posts = EXCLUDED.low_posts,
                    raw_sections = EXCLUDED.raw_sections,
                    updated_at = now()
                RETURNING id
                """
            ),
            data,
        ).mappings().one()
        return row["id"]

    def upsert_tiktok_report(self, conn, table, data):
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_followers, total_views, reach, total_engagement,
                    engagement_rate, likes, comments, shares, total_posts,
                    video_posts, top_posts, low_posts, raw_sections
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :views, :reach, :engagement,
                    :engagement_rate, :likes, :comments, :shares, :posts,
                    :posts, CAST(:top_posts AS JSONB), CAST(:low_posts AS JSONB),
                    CAST(:raw_sections AS JSONB)
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_followers = EXCLUDED.total_followers,
                    total_views = EXCLUDED.total_views,
                    reach = EXCLUDED.reach,
                    total_engagement = EXCLUDED.total_engagement,
                    engagement_rate = EXCLUDED.engagement_rate,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    shares = EXCLUDED.shares,
                    total_posts = EXCLUDED.total_posts,
                    video_posts = EXCLUDED.video_posts,
                    top_posts = EXCLUDED.top_posts,
                    low_posts = EXCLUDED.low_posts,
                    raw_sections = EXCLUDED.raw_sections,
                    updated_at = now()
                RETURNING id
                """
            ),
            data,
        ).mappings().one()
        return row["id"]

    def upsert_youtube_report(self, conn, table, data):
        row = conn.execute(
            text(
                f"""
                INSERT INTO {table} (
                    client_id, profile_id, report_period_id, source,
                    total_subscribers, total_views, total_engagement,
                    engagement_rate, likes, comments, shares, total_posts,
                    video_posts, top_posts, low_posts, raw_sections
                )
                VALUES (
                    :client_id, :profile_id, :period_id, 'fanpage_karma_csv',
                    :followers, :views, :engagement,
                    :engagement_rate, :likes, :comments, :shares, :posts,
                    :posts, CAST(:top_posts AS JSONB), CAST(:low_posts AS JSONB),
                    CAST(:raw_sections AS JSONB)
                )
                ON CONFLICT (client_id, profile_id, report_period_id)
                DO UPDATE SET
                    total_subscribers = EXCLUDED.total_subscribers,
                    total_views = EXCLUDED.total_views,
                    total_engagement = EXCLUDED.total_engagement,
                    engagement_rate = EXCLUDED.engagement_rate,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    shares = EXCLUDED.shares,
                    total_posts = EXCLUDED.total_posts,
                    video_posts = EXCLUDED.video_posts,
                    top_posts = EXCLUDED.top_posts,
                    low_posts = EXCLUDED.low_posts,
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
                        total_followers, total_posts, total_engagement,
                        engagement_rate, profile_url, image_url, raw_metrics
                    )
                    VALUES (
                        :client_id, :competitor_id, :profile_id,
                        :period_id, :platform, 'fanpage_karma_csv', :profile_name,
                        :followers, :posts, :engagement,
                        :engagement_rate, :profile_url, :image_url, CAST(:raw_metrics AS JSONB)
                    )
                    ON CONFLICT (client_id, platform, report_period_id, profile_name)
                    DO UPDATE SET
                        competitor_id = EXCLUDED.competitor_id,
                        competitor_profile_id = EXCLUDED.competitor_profile_id,
                        total_followers = EXCLUDED.total_followers,
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

    def upsert_kpi_results_from_reports(self, conn, client_id, period_id, reports):
        count = 0
        for platform, report in reports.items():
            metric_values = {
                "followers": report.get("followers"),
                "subscribers": report.get("followers"),
                "engagement": report.get("engagement"),
                "reach": report.get("reach"),
                "views": report.get("views"),
            }
            for metric_name in PLATFORM_KPI_METRICS[platform]:
                actual = metric_values.get(metric_name)
                if actual is None:
                    continue
                target = conn.execute(
                    text(
                        """
                        SELECT id, target_month, target_year, unit
                        FROM kpi_targets
                        WHERE client_id = :client_id
                          AND platform = :platform
                          AND metric_name = :metric_name
                          AND period_year = EXTRACT(YEAR FROM (SELECT period_start FROM report_periods WHERE id = :period_id))
                        """
                    ),
                    {
                        "client_id": client_id,
                        "platform": platform,
                        "metric_name": metric_name,
                        "period_id": period_id,
                    },
                ).mappings().first()
                target_month = target["target_month"] if target else None
                target_year = target["target_year"] if target else None
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
                            :platform, :metric_name, :actual, :actual,
                            :target_month, :target_year,
                            CASE WHEN CAST(:target_month AS NUMERIC) IS NOT NULL AND CAST(:target_month AS NUMERIC) <> 0
                                 THEN ROUND((CAST(:actual AS NUMERIC) / CAST(:target_month AS NUMERIC)) * 100, 2)
                                 ELSE NULL END,
                            CASE WHEN CAST(:target_year AS NUMERIC) IS NOT NULL AND CAST(:target_year AS NUMERIC) <> 0
                                 THEN ROUND((CAST(:actual AS NUMERIC) / CAST(:target_year AS NUMERIC)) * 100, 2)
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
                        "target_id": target["id"] if target else None,
                        "platform": platform,
                        "metric_name": metric_name,
                        "actual": actual,
                        "target_month": target_month,
                        "target_year": target_year,
                        "unit": target["unit"] if target else None,
                        "source_table": PLATFORM_TABLES[platform],
                        "source_id": report.get("report_id"),
                    },
                )
                count += 1
        return count


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
            metric("Growth Rate", report.get("follower_growth_rate"), "%"),
            metric("Views", report.get("total_views")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    return [
        metric("Followers", report.get("total_followers")),
        metric("Growth Rate", report.get("follower_growth_rate"), "%"),
        metric("Reach", report.get("reach")),
        metric("Engagement", report.get("total_engagement")),
        metric("Eng. Rate", report.get("engagement_rate"), "%"),
        metric("Posts", report.get("total_posts")),
    ]


def metric(label: str, value, suffix: str = ""):
    return {"label": label, "value": value, "suffix": suffix}


class DashboardHandler(SimpleHTTPRequestHandler):
    repository = DashboardRepository()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/clients":
            self.send_json(self.repository.clients())
            return
        if parsed.path.startswith("/api/clients/"):
            parts = [part for part in parsed.path.split("/") if part]
            try:
                if len(parts) == 4 and parts[1] == "clients" and parts[3] == "platforms":
                    self.send_json(self.repository.platforms(parts[2]))
                    return
                if (
                    len(parts) == 6
                    and parts[1] == "clients"
                    and parts[3] == "platforms"
                    and parts[5] == "overview"
                ):
                    self.send_json(self.repository.overview(parts[2], parts[4]))
                    return
            except ValueError as exc:
                self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
                return
        if parsed.path == "/":
            self.path = "/index.html"
        elif not parsed.path.startswith("/api/") and "." not in Path(parsed.path).name:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/clients":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                self.send_json(self.repository.create_client(payload), HTTPStatus.CREATED)
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                message = str(exc)
                if "duplicate key value" in message and "clients_client_code_key" in message:
                    message = "Client code already exists."
                self.send_error_json(message, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/import/csv":
            try:
                fields = self.parse_multipart()
                payload = {
                    "client_id": fields.get("client_id"),
                    "month_slug": fields.get("month_slug"),
                }
                files = {slot: fields.get(slot) for slot in CSV_IMPORT_SLOTS}
                self.send_json(self.repository.import_csv_report(payload, files), HTTPStatus.CREATED)
            except ValueError as exc:
                self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path != "/api/kpi-targets":
            self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            self.send_json(self.repository.upsert_kpi_target(payload), HTTPStatus.CREATED)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2 and parts[0] == "api" and parts[1] == "clients":
            self.send_error_json("Client id is required", HTTPStatus.BAD_REQUEST)
            return
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "clients":
            try:
                self.send_json(self.repository.delete_client(parts[2]))
            except ValueError as exc:
                self.send_error_json(str(exc), HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def parse_multipart(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("Expected multipart/form-data")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        fields = {}
        for key in form.keys():
            item = form[key]
            if isinstance(item, list):
                item = item[0]
            fields[key] = item if getattr(item, "filename", None) else item.value
        return fields

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(json_safe(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status=HTTPStatus.INTERNAL_SERVER_ERROR):
        self.send_json({"error": message}, status)


def main():
    query = parse_qs(urlparse(os.environ.get("DASHBOARD_QUERY", "")).query)
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT") or query.get("port", [8000])[0])
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
