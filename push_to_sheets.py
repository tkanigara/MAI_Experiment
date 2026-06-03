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
    "instagram_account_raw": [
        "run_id",
        "client_id",
        "frequency",
        "ingested_at",
        "source_file",
        "raw_json",
    ],
    "instagram_media_raw": [
        "run_id",
        "client_id",
        "frequency",
        "ingested_at",
        "source_file",
        "media_id",
        "timestamp",
        "permalink",
        "raw_json",
    ],
    "instagram_kpi_processed": [
        "run_id",
        "client_id",
        "frequency",
        "processed_at",
        "source_file",
        "account_source_file",
        "total_posts",
        "total_reach",
        "total_views",
        "total_likes",
        "total_comments",
        "total_shares",
        "total_saved",
        "total_interactions",
        "avg_engagement_rate",
        "best_content_type",
        "feed_stats_json",
        "reels_stats_json",
        "top_3_content_json",
        "kpi_json",
    ],
    "ai_insights": [
        "run_id",
        "client_id",
        "frequency",
        "generated_at",
        *REQUIRED_FIELDS,
        "warning",
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


def build_media_rows(run_id, client_id, frequency, media_csv):
    rows = []
    ingested_at = utc_now()
    for row in read_csv_dicts(media_csv):
        rows.append(
            [
                run_id,
                client_id,
                frequency,
                ingested_at,
                str(media_csv),
                row.get("id", ""),
                row.get("timestamp", ""),
                row.get("permalink", ""),
                dumps_compact(row),
            ]
        )
    return rows


def build_account_rows(run_id, client_id, frequency, account_csv):
    rows = []
    ingested_at = utc_now()
    for row in read_csv_dicts(account_csv):
        rows.append([run_id, client_id, frequency, ingested_at, str(account_csv), dumps_compact(row)])
    return rows


def build_kpi_row(run_id, client_id, frequency, kpi_summary):
    return [
        run_id,
        client_id,
        frequency,
        utc_now(),
        kpi_summary.get("source_file", ""),
        kpi_summary.get("account_source_file", ""),
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
        dumps_compact(kpi_summary.get("feed_stats", {})),
        dumps_compact(kpi_summary.get("reels_stats", {})),
        dumps_compact(kpi_summary.get("top_3_content", [])),
        dumps_compact(kpi_summary),
    ]


def build_insight_row(run_id, client_id, frequency, ai_insights):
    return [
        run_id,
        client_id,
        frequency,
        utc_now(),
        *[ai_insights.get(field, "") for field in REQUIRED_FIELDS],
        ai_insights.get("warning", ""),
        dumps_compact(ai_insights),
    ]


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
    append_rows(service, spreadsheet_id, "instagram_account_raw", build_account_rows(run_id, client_id, frequency, account_csv))
    append_rows(service, spreadsheet_id, "instagram_media_raw", build_media_rows(run_id, client_id, frequency, media_csv))
    append_rows(service, spreadsheet_id, "instagram_kpi_processed", [build_kpi_row(run_id, client_id, frequency, kpi_summary)])
    append_rows(service, spreadsheet_id, "ai_insights", [build_insight_row(run_id, client_id, frequency, ai_insights)])
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
