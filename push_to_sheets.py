import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

from ai_insight_pipeline import REQUIRED_FIELDS
from analytics_pipeline import dumps_compact


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_INTERMEDIATE_SPREADSHEET_ID = "1Bp-msgx3dieEHyfw0xHDPYLGHTA47_or2PTPJJVbiCA"
DEFAULT_SERVICE_ACCOUNT_FILE = "optimum-essence-497706-i6-1c879e7ef3bd.json"

INTERMEDIATE_HEADERS = {
    "instagram": [
        "run_id",
        "client_id",
        "client_name",
        "frequency",
        "processed_at",
        "platform",
        "account_id",
        "account_username",
        "account_name",
        "followers_count",
        "media_id",
        "posted_at",
        "caption",
        "content_type",
        "media_type",
        "media_product_type",
        "permalink",
        "media_url",
        "thumbnail_url",
        "reach",
        "views",
        "likes",
        "comments",
        "shares",
        "saved",
        "interactions",
        "engagement_rate",
        "post_rank_by_interactions",
        "is_top_3_content",
        "period_total_posts",
        "period_total_reach",
        "period_total_views",
        "period_total_likes",
        "period_total_comments",
        "period_total_shares",
        "period_total_saved",
        "period_total_interactions",
        "period_avg_engagement_rate",
        "best_content_type",
        "feed_posts",
        "feed_reach",
        "feed_interactions",
        "reels_posts",
        "reels_reach",
        "reels_interactions",
        *REQUIRED_FIELDS,
        "warning",
        "media_source_file",
        "account_source_file",
        "post_json",
        "insight_json",
    ],
    "facebook": [
        "run_id",
        "client_id",
        "client_name",
        "frequency",
        "processed_at",
        "platform",
        "post_id",
        "posted_at",
        "content_type",
        "caption",
        "permalink",
        "reach",
        "views",
        "interactions",
        "insight_json",
    ],
    "youtube": [
        "run_id",
        "client_id",
        "client_name",
        "frequency",
        "processed_at",
        "platform",
        "video_id",
        "posted_at",
        "title",
        "content_type",
        "permalink",
        "views",
        "likes",
        "comments",
        "interactions",
        "insight_json",
    ],
    "tiktok": [
        "run_id",
        "client_id",
        "client_name",
        "frequency",
        "processed_at",
        "platform",
        "video_id",
        "posted_at",
        "caption",
        "content_type",
        "permalink",
        "views",
        "likes",
        "comments",
        "shares",
        "interactions",
        "insight_json",
    ],
    "report_runs": [
        "run_id",
        "client_id",
        "frequency",
        "started_at",
        "completed_at",
        "status",
        "media_csv",
        "account_csv",
        "slides_url",
        "warning",
        "error",
    ],
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def env_value(name, default=""):
    value = os.getenv(name, default).strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def get_sheets_service(credentials_file=None):
    credentials_path = Path(
        credentials_file
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", DEFAULT_SERVICE_ACCOUNT_FILE).strip()
    )
    if not credentials_path.exists():
        raise FileNotFoundError(f"Google service account file not found: {credentials_path}")
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=credentials)


def sheet_metadata(service, spreadsheet_id):
    return (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
        .execute()
    )


def existing_tabs(service, spreadsheet_id):
    metadata = sheet_metadata(service, spreadsheet_id)
    return {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in metadata.get("sheets", [])
    }


def ensure_tabs(service, spreadsheet_id):
    tabs = existing_tabs(service, spreadsheet_id)
    requests = []
    for title in INTERMEDIATE_HEADERS:
        if title not in tabs:
            requests.append({"addSheet": {"properties": {"title": title}}})
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    for title, headers in INTERMEDIATE_HEADERS.items():
        current = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{title}!1:1")
            .execute()
            .get("values", [])
        )
        if not current or current[0] != headers:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{title}!1:1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()


def append_rows(service, spreadsheet_id, tab, rows):
    if not rows:
        return
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


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


def post_metrics(row):
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
        "reach": reach,
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saved": saved,
        "interactions": interactions,
        "engagement_rate": engagement_rate,
    }


def build_instagram_ready_rows(run_id, client_id, frequency, media_csv, kpi_summary, ai_insights):
    rows = []
    processed_at = utc_now()
    media_rows = read_csv_dicts(media_csv)
    account = kpi_summary.get("account", {})
    client_name = (
        os.getenv("REPORT_CLIENT_NAME", "").strip()
        or account.get("name")
        or account.get("username")
        or client_id
    )
    feed_stats = kpi_summary.get("feed_stats", {})
    reels_stats = kpi_summary.get("reels_stats", {})
    ranked_media = []
    for row in media_rows:
        metrics = post_metrics(row)
        ranked_media.append((row, metrics))
    ranked_media.sort(key=lambda item: (item[1]["interactions"], item[1]["reach"]), reverse=True)
    rank_by_id = {str(row.get("id", "")): index for index, (row, _) in enumerate(ranked_media, start=1)}

    for row, metrics in ranked_media:
        media_id = str(row.get("id", ""))
        rank = rank_by_id.get(media_id, "")
        rows.append(
            [
                run_id,
                client_id,
                client_name,
                frequency,
                processed_at,
                "instagram",
                account.get("id", ""),
                account.get("username", ""),
                account.get("name", ""),
                account.get("followers_count", 0),
                media_id,
                row.get("timestamp", ""),
                row.get("caption", ""),
                normalize_content_type(row),
                row.get("media_type", ""),
                row.get("media_product_type", ""),
                row.get("permalink", ""),
                row.get("media_url", ""),
                row.get("thumbnail_url", ""),
                metrics["reach"],
                metrics["views"],
                metrics["likes"],
                metrics["comments"],
                metrics["shares"],
                metrics["saved"],
                metrics["interactions"],
                metrics["engagement_rate"],
                rank,
                "yes" if rank and rank <= 3 else "no",
                kpi_summary.get("total_posts", 0),
                kpi_summary.get("total_reach", 0),
                kpi_summary.get("total_views", 0),
                kpi_summary.get("total_likes", 0),
                kpi_summary.get("total_comments", 0),
                kpi_summary.get("total_shares", 0),
                kpi_summary.get("total_saved", 0),
                kpi_summary.get("total_interactions", 0),
                kpi_summary.get("avg_engagement_rate", 0),
                kpi_summary.get("best_content_type", ""),
                feed_stats.get("posts", 0),
                feed_stats.get("reach", 0),
                feed_stats.get("total_interactions", 0),
                reels_stats.get("posts", 0),
                reels_stats.get("reach", 0),
                reels_stats.get("total_interactions", 0),
                *[ai_insights.get(field, "") for field in REQUIRED_FIELDS],
                ai_insights.get("warning", ""),
                kpi_summary.get("source_file", str(media_csv or "")),
                kpi_summary.get("account_source_file", ""),
                dumps_compact(row),
                dumps_compact(ai_insights),
            ]
        )
    return rows


def build_report_run_row(
    run_id,
    client_id,
    frequency,
    started_at,
    status,
    media_csv="",
    account_csv="",
    slides_url="",
    warning="",
    error="",
):
    return [
        run_id,
        client_id,
        frequency,
        started_at,
        utc_now(),
        status,
        str(media_csv or ""),
        str(account_csv or ""),
        slides_url,
        warning,
        error,
    ]


def push_intermediate_run(
    run_id,
    client_id,
    frequency,
    media_csv,
    account_csv,
    kpi_summary,
    ai_insights,
    spreadsheet_id=None,
    credentials_file=None,
):
    spreadsheet_id = spreadsheet_id or env_value(
        "INTERMEDIATE_SPREADSHEET_ID",
        DEFAULT_INTERMEDIATE_SPREADSHEET_ID,
    )
    service = get_sheets_service(credentials_file)
    ensure_tabs(service, spreadsheet_id)
    append_rows(
        service,
        spreadsheet_id,
        "instagram",
        build_instagram_ready_rows(
            run_id,
            client_id,
            frequency,
            media_csv,
            kpi_summary,
            ai_insights,
        ),
    )
    return service


def append_report_run(
    run_id,
    client_id,
    frequency,
    started_at,
    status,
    media_csv="",
    account_csv="",
    slides_url="",
    warning="",
    error="",
    spreadsheet_id=None,
    credentials_file=None,
    service=None,
):
    spreadsheet_id = spreadsheet_id or env_value(
        "INTERMEDIATE_SPREADSHEET_ID",
        DEFAULT_INTERMEDIATE_SPREADSHEET_ID,
    )
    service = service or get_sheets_service(credentials_file)
    ensure_tabs(service, spreadsheet_id)
    append_rows(
        service,
        spreadsheet_id,
        "report_runs",
        [
            build_report_run_row(
                run_id,
                client_id,
                frequency,
                started_at,
                status,
                media_csv,
                account_csv,
                slides_url,
                warning,
                error,
            )
        ],
    )
