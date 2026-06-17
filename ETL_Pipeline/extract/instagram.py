import os
from datetime import datetime, timezone
from pathlib import Path

from ETL_Pipeline.extract.meta_instagram import (
    DEFAULT_API_VERSION,
    MetaClient,
    env_required,
    export_instagram,
    export_instagram_account,
    write_csv,
)
from ETL_Pipeline.extract.report_period import resolve_period


def platform_folder(output_root, client_id, platform="instagram"):
    safe_client = "".join(char if char.isalnum() or char in "-_" else "_" for char in client_id)
    folder = Path(output_root) / safe_client / platform
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def extract_instagram_raw(
    client_id,
    run_id,
    frequency,
    limit=5,
    since=None,
    until=None,
    month=None,
    output_root="data",
    ig_business_id=None,
):
    """Extract Instagram account and media data to raw CSV files.

    Output structure:
    data/<client_id>/instagram/instagram_account_raw_<run_id>.csv
    data/<client_id>/instagram/instagram_media_raw_<run_id>.csv
    """
    period = resolve_period(month=month, since=since, until=until)
    since = period.since or None
    until = period.until or None
    file_period = f"_{period.month}" if period.month else ""
    period_columns = {
        "report_month": period.month,
        "report_since": period.since,
        "report_until": period.until,
    }

    token = env_required("META_ACCESS_TOKEN")
    ig_business_id = ig_business_id or env_required("IG_BUSINESS_ID")
    api_version = os.environ.get("META_API_VERSION", DEFAULT_API_VERSION).strip()
    client = MetaClient(token, api_version)
    output_dir = platform_folder(output_root, client_id, "instagram")
    extracted_at = datetime.now(timezone.utc).isoformat()

    account_rows = export_instagram_account(client, ig_business_id, since, until)
    for row in account_rows:
        row.update(period_columns)
    account_csv = output_dir / f"instagram_account_raw{file_period}_{run_id}.csv"
    write_csv(account_csv, account_rows)

    media_rows = export_instagram(client, ig_business_id, limit, since, until)
    for row in media_rows:
        row.update(period_columns)
    if account_rows:
        audience_columns = [
            "raw_demographic_age_gender",
            "raw_demographic_country",
            "raw_reached_demographic_age_gender",
            "raw_reached_demographic_country",
        ]
        audience_data = {
            f"account_{column}": account_rows[0].get(column, "")
            for column in audience_columns
            if account_rows[0].get(column, "")
        }
        if audience_data:
            audience_data["audience_demographic_source"] = "instagram_account_insights"
            for row in media_rows:
                row.update(audience_data)

    media_csv = output_dir / f"instagram_media_raw{file_period}_{run_id}.csv"
    write_csv(media_csv, media_rows)

    return {
        "client_id": client_id,
        "platform": "instagram",
        "frequency": frequency,
        "run_id": run_id,
        "extracted_at": extracted_at,
        "report_month": period.month,
        "report_since": period.since,
        "report_until": period.until,
        "account_csv": account_csv,
        "media_csv": media_csv,
        "output_dir": output_dir,
    }
