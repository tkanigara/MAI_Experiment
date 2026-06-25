import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


DEFAULT_TEMPLATE_URL = (
    "https://docs.google.com/presentation/d/"
    "1VL_VaXXyC3AI-Sk3ajSO-hAX0y14yLxhRREUFGw9u6g/edit?usp=sharing"
)
DEFAULT_DATA_DIR = Path("data")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def default_template():
    return (
        os.getenv("SLIDES_TEMPLATE_ID")
        or os.getenv("GOOGLE_SLIDES_TEMPLATE_ID")
        or DEFAULT_TEMPLATE_URL
    )


def default_slides_credentials():
    auth_mode = os.getenv("GOOGLE_SLIDES_AUTH", "").strip().lower()
    if auth_mode in ("oauth", "user_oauth", "user-oauth"):
        return os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    return (
        os.getenv("GOOGLE_SLIDES_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    )

AI_PLACEHOLDER_KEYS = {
    "executive_summary": "{{EXECUTIVE_SUMMARY}}",
    "ig_reach_insight_summary": "{{IG_REACH_INSIGHT_SUMMARY}}",
    "ig_performance_insight": "{{IG_PERFORMANCE_INSIGHT}}",
    "engagement_trend_text": "{{ENGAGEMENT_TREND_TEXT}}",
    "benchmark_note": "{{BENCHMARK_NOTE}}",
    "top_content_success_driver": "{{TOP_CONTENT_SUCCESS_DRIVER}}",
    "content_type_insight": "{{CONTENT_TYPE_INSIGHT}}",
    "competitor_strategy_insight": "{{COMPETITOR_STRATEGY_INSIGHT}}",
    "summary_point_1": "{{SUMMARY_POINT_1}}",
    "summary_point_2": "{{SUMMARY_POINT_2}}",
    "summary_point_3": "{{SUMMARY_POINT_3}}",
    "summary_point_4": "{{SUMMARY_POINT_4}}",
    "recommendation_1": "{{RECOMMENDATION_1}}",
    "recommendation_2": "{{RECOMMENDATION_2}}",
    "recommendation_3": "{{RECOMMENDATION_3}}",
    "ai_insight_1": "{{AI_INSIGHT_1}}",
    "ai_insight_2": "{{AI_INSIGHT_2}}",
    "ai_insight_3": "{{AI_INSIGHT_3}}",
    "ai_recommendation_1": "{{AI_RECOMMENDATION_1}}",
    "ai_recommendation_2": "{{AI_RECOMMENDATION_2}}",
    "ai_recommendation_3": "{{AI_RECOMMENDATION_3}}",
}


def extract_presentation_id(value):
    """Ambil presentation ID dari URL Google Slides atau ID polos."""
    match = re.search(r"/presentation/d/([^/]+)", value)
    if match:
        return match.group(1)
    return value.strip()


def default_data_dir():
    return Path(os.getenv("DATA_FOLDER", DEFAULT_DATA_DIR))


def report_period_to_month(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return value
    for fmt in ("%B %Y", "%b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    return ""


def latest_instagram_csv(data_dir, client_id=None, report_month=None):
    data_dir = Path(data_dir)
    search_root = data_dir
    if client_id:
        client_root = data_dir / client_id / "instagram"
        if client_root.exists():
            search_root = client_root

    files = []
    for pattern in ("instagram_media_raw*.csv", "instagram_media_*.csv"):
        files.extend(search_root.rglob(pattern))
    files = sorted(set(files), key=lambda path: path.stat().st_mtime)

    if client_id and search_root == data_dir:
        files = [path for path in files if client_id in path.parts]

    if report_month:
        files = [path for path in files if report_period_from_media_csv(path) == report_month]

    if not files:
        client_note = f" untuk client '{client_id}'" if client_id else ""
        period_note = f" periode {report_month}" if report_month else ""
        raise FileNotFoundError(
            f"Tidak ada file instagram_media_*.csv{client_note}{period_note} di {data_dir}"
        )
    return files[-1]


def latest_optional_csv(data_dir, pattern):
    files = sorted(Path(data_dir).rglob(pattern), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def latest_account_csv_for_media(media_csv_path):
    media_csv_path = Path(media_csv_path)
    current_period = report_period_from_media_csv(media_csv_path)
    files = sorted(
        media_csv_path.parent.glob("instagram_account_*.csv"),
        key=lambda path: path.stat().st_mtime,
    )
    if current_period:
        period_files = [
            path for path in files if report_period_from_account_csv(path) == current_period
        ]
        if period_files:
            return period_files[-1]
    return files[-1] if files else None


def extract_run_stamp(path):
    match = re.search(r"_(\d{8})_(\d{6})(?:\.csv)?$", Path(path).name)
    if not match:
        return None
    return datetime.strptime("_".join(match.groups()), "%Y%m%d_%H%M%S")


def report_period_from_filename(path):
    match = re.search(r"_raw_(\d{4}-\d{2})_", Path(path).name)
    return match.group(1) if match else ""


def report_period_from_media_csv(path):
    filename_period = report_period_from_filename(path)
    if filename_period:
        return filename_period

    try:
        df = pd.read_csv(path, usecols=lambda col: col == "timestamp")
    except Exception:
        return ""
    if df.empty or "timestamp" not in df.columns:
        return ""

    periods = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    periods = periods.dropna()
    if periods.empty:
        return ""
    return periods.dt.tz_convert(None).dt.to_period("M").mode().iloc[0].strftime("%Y-%m")


def report_period_from_account_csv(path):
    filename_period = report_period_from_filename(path)
    if filename_period:
        return filename_period

    try:
        df = pd.read_csv(path, usecols=lambda col: col in ("report_month", "snapshot_date"))
    except Exception:
        return ""
    if df.empty:
        return ""
    row = df.iloc[-1]
    if row.get("report_month"):
        return str(row.get("report_month"))
    if row.get("snapshot_date"):
        parsed = pd.to_datetime(row.get("snapshot_date"), errors="coerce")
        if not pd.isna(parsed):
            return parsed.to_period("M").strftime("%Y-%m")
    return ""


def client_from_data_path(path):
    parts = Path(path).parts
    if "data" in parts:
        index = parts.index("data")
        if index + 1 < len(parts):
            return parts[index + 1]
    return ""


def latest_files_by_period(folder, pattern, period_func):
    result = {}
    for path in Path(folder).glob(pattern):
        period = period_func(path)
        if not period:
            continue
        stamp = extract_run_stamp(path) or datetime.fromtimestamp(path.stat().st_mtime)
        current = result.get(period)
        if not current or stamp > current[0]:
            result[period] = (stamp, path)
    return {period: item[1] for period, item in result.items()}


def read_sheet_records(sheet_name):
    spreadsheet_id = os.getenv("INTERMEDIATE_SPREADSHEET_ID", "").strip()
    credentials_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not spreadsheet_id or not credentials_file:
        return pd.DataFrame()

    try:
        import gspread
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=SHEETS_SCOPES,
        )
        client = gspread.authorize(credentials)
        worksheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        records = worksheet.get_all_records()
    except Exception as exc:
        print(f"[Slides] Skip reading sheet '{sheet_name}': {exc}", file=sys.stderr)
        return pd.DataFrame()

    return pd.DataFrame(records)


def sheet_long_to_month_rows(df, client_name, platform="instagram"):
    if df.empty:
        return []

    df = df.copy()
    client_col = "client_id" if "client_id" in df.columns else "client"
    if client_col in df.columns:
        df = df[df[client_col].astype(str) == str(client_name)]
    if "platform" in df.columns:
        df = df[df["platform"].astype(str).str.lower() == platform.lower()]
    if df.empty or not {"year", "month", "metric", "value"}.issubset(df.columns):
        return []

    df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)
    df["month"] = pd.to_numeric(df["month"], errors="coerce").fillna(0).astype(int)
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    rows = []
    for (year, month), group in df.groupby(["year", "month"]):
        if not year or not month:
            continue
        metrics = {
            str(row["metric"]): number(row["value"])
            for _, row in group.iterrows()
        }
        period = f"{year:04d}-{month:02d}"
        rows.append({
            "period": period,
            "name": datetime(year, month, 1).strftime("%b"),
            **metrics,
        })
    return sorted(rows, key=lambda row: row["period"], reverse=True)


def merge_sheet_monthly_rows(kpi, client_name, current_period):
    followers_rows = sheet_long_to_month_rows(
        read_sheet_records("foll_growth"),
        client_name,
    )
    engagement_rows = sheet_long_to_month_rows(
        read_sheet_records("engagement_performance"),
        client_name,
    )
    if not followers_rows and not engagement_rows:
        return kpi

    by_period = {}
    for row in engagement_rows:
        by_period.setdefault(row["period"], {}).update({
            "period": row["period"],
            "name": row["name"],
            "posts": row.get("number_of_post", 0),
            "impr": row.get("impressions", 0),
            "reach": row.get("reach", 0),
            "likes": row.get("likes", 0),
            "comm": row.get("comments", 0),
            "share": row.get("shares", 0),
            "interactions": row.get("total_engagement", 0),
            "er": row.get("er", 0),
        })
    for row in followers_rows:
        by_period.setdefault(row["period"], {}).update({
            "period": row["period"],
            "name": row["name"],
            "followers": row.get("total_followers", 0),
            "follows": row.get("follows", 0),
            "net_growth": row.get("net_growth", 0),
            "unfollows": row.get("unfollows", 0),
        })

    periods = sorted(
        [period for period in by_period if not current_period or period <= current_period],
        reverse=True,
    )[:3]
    monthly_rows = [by_period[period] for period in periods]
    if monthly_rows:
        current = monthly_rows[0]
        kpi["monthly_rows"] = monthly_rows
        kpi["total_posts"] = current.get("posts", kpi.get("total_posts", 0))
        kpi["total_reach"] = current.get("reach", kpi.get("total_reach", 0))
        kpi["total_views"] = current.get("impr", kpi.get("total_views", 0))
        kpi["total_interactions"] = current.get("interactions", kpi.get("total_interactions", 0))
        kpi["total_likes"] = current.get("likes", kpi.get("total_likes", 0))
        kpi["total_comments"] = current.get("comm", kpi.get("total_comments", 0))
        kpi["total_shares"] = current.get("share", kpi.get("total_shares", 0))
        kpi["avg_engagement_rate"] = current.get("er", kpi.get("avg_engagement_rate", 0))
        if current.get("followers"):
            kpi.setdefault("account", {})["followers_count"] = current.get("followers")
        if current.get("follows"):
            kpi.setdefault("account", {})["follows_count"] = current.get("follows")
    return kpi


def number(value):
    if pd.isna(value):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def json_safe(value):
    """Convert pandas/numpy values into JSON-serializable Python values."""
    if isinstance(value, dict):
        return {str(key): json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def fmt_number(value):
    return f"{int(round(number(value))):,}"


def fmt_percent(value):
    return f"{number(value):.2f}%"


def pct(actual, target):
    actual = number(actual)
    target = number(target)
    if not target:
        return "-"
    return fmt_percent(actual / target * 100)


def safe_divide_percent(numerator, denominator):
    numerator = number(numerator)
    denominator = number(denominator)
    if not denominator:
        return 0
    return numerator / denominator * 100


def first_available(row, columns, default=""):
    for column in columns:
        if column in row and not pd.isna(row[column]):
            return row[column]
    return default


def truncate_text(value, max_chars=80):
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def parse_json_cell(value):
    if value is None or pd.isna(value) or not str(value).strip():
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def find_breakdown_results(payload):
    """Cari result demographic dari bentuk response Meta yang bisa berubah."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            if "dimension_values" in value and "value" in value:
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return found


def normalize_demographics(account_row):
    age_totals = {}
    gender_totals = {}
    city_totals = {}

    for column in ["raw_demographic_age_gender", "raw_reached_demographic_age_gender"]:
        payload = parse_json_cell(account_row.get(column))
        for item in find_breakdown_results(payload):
            dimensions = item.get("dimension_values", [])
            value = number(item.get("value", 0))
            for dimension in dimensions:
                label = str(dimension)
                if "-" in label or label.endswith("+"):
                    age_totals[label] = age_totals.get(label, 0) + value
                elif label.upper() in {"M", "MALE", "F", "FEMALE", "U", "UNKNOWN"}:
                    gender_totals[label.upper()] = gender_totals.get(label.upper(), 0) + value

    for column in ["raw_demographic_city", "raw_reached_demographic_city"]:
        payload = parse_json_cell(account_row.get(column))
        for item in find_breakdown_results(payload):
            dimensions = item.get("dimension_values", [])
            if not dimensions:
                continue
            city = str(dimensions[0])
            city_totals[city] = city_totals.get(city, 0) + number(item.get("value", 0))

    def pct_of(total_map, key):
        total = sum(total_map.values())
        return safe_divide_percent(total_map.get(key, 0), total) if total else 0

    city_total = sum(city_totals.values())
    top_cities = sorted(city_totals.items(), key=lambda item: item[1], reverse=True)[:3]

    return {
        "age_18_24_pct": pct_of(age_totals, "18-24"),
        "age_25_34_pct": pct_of(age_totals, "25-34"),
        "age_35_44_pct": pct_of(age_totals, "35-44"),
        "age_45_plus_pct": sum(pct_of(age_totals, key) for key in ["45-54", "55-64", "65+"]),
        "gender_male_pct": pct_of(gender_totals, "M") or pct_of(gender_totals, "MALE"),
        "gender_female_pct": pct_of(gender_totals, "F") or pct_of(gender_totals, "FEMALE"),
        "top_cities": [
            {"city": city, "pct": safe_divide_percent(value, city_total)}
            for city, value in top_cities
        ],
    }


def load_instagram_account(account_csv_path):
    if not account_csv_path or not Path(account_csv_path).exists():
        return {}

    df = pd.read_csv(account_csv_path)
    if df.empty:
        return {}

    row = df.iloc[-1].to_dict()
    return {
        "source_file": str(account_csv_path),
        "followers_count": number(row.get("followers_count", 0)),
        "follows_count": number(row.get("follows_count", 0)),
        "media_count": number(row.get("media_count", 0)),
        "username": row.get("username", ""),
        "name": row.get("name", ""),
        "insight_reach": number(row.get("insight_reach", 0)),
        "insight_views": number(row.get("insight_views", 0)),
        "insight_impressions": number(row.get("insight_impressions", 0)),
        "insight_profile_views": number(row.get("insight_profile_views", 0)),
        "insight_website_clicks": number(row.get("insight_website_clicks", 0)),
        "insight_accounts_engaged": number(row.get("insight_accounts_engaged", 0)),
        "insight_total_interactions": number(row.get("insight_total_interactions", 0)),
        "demographics": normalize_demographics(row),
    }


def calculate_instagram_kpi(csv_path, account_csv_path=None):
    """Hitung KPI sederhana dari CSV hasil meta_export.py."""
    df = pd.read_csv(csv_path)
    account = load_instagram_account(account_csv_path)

    metric_columns = {
        "reach": "insight_reach",
        "views": "insight_views",
        "interactions": "insight_total_interactions",
        "likes": "insight_likes",
        "comments": "insight_comments",
        "shares": "insight_shares",
        "saved": "insight_saved",
    }

    for column in metric_columns.values():
        if column not in df.columns:
            df[column] = 0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    total_posts = len(df)
    total_reach = df[metric_columns["reach"]].sum()
    total_views = df[metric_columns["views"]].sum()
    total_interactions = df[metric_columns["interactions"]].sum()
    avg_er = (total_interactions / total_reach * 100) if total_reach else 0
    total_likes = df[metric_columns["likes"]].sum()
    total_comments = df[metric_columns["comments"]].sum()
    total_shares = df[metric_columns["shares"]].sum()
    total_saved = df[metric_columns["saved"]].sum()

    if "timestamp" in df.columns:
        timestamps = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df["_period"] = timestamps.dt.tz_convert(None).dt.to_period("M")
        monthly_df = (
            df.dropna(subset=["_period"])
            .groupby("_period")
            .agg(
                posts=("id", "count") if "id" in df.columns else (metric_columns["reach"], "count"),
                impr=(metric_columns["views"], "sum"),
                reach=(metric_columns["reach"], "sum"),
                likes=(metric_columns["likes"], "sum"),
                comm=(metric_columns["comments"], "sum"),
                share=(metric_columns["shares"], "sum"),
                interactions=(metric_columns["interactions"], "sum"),
            )
            .tail(3)
        )
    else:
        monthly_df = pd.DataFrame()

    monthly_rows = []
    for period, row in monthly_df.iterrows():
        monthly_rows.append(
            {
                "name": period.strftime("%b"),
                "posts": row["posts"],
                "impr": row["impr"],
                "reach": row["reach"],
                "likes": row["likes"],
                "comm": row["comm"],
                "share": row["share"],
                "er": safe_divide_percent(row["interactions"], row["reach"]),
            }
        )

    if total_posts:
        top_df = df.sort_values(
            by=[metric_columns["interactions"], metric_columns["reach"]],
            ascending=False,
        ).head(3)
    else:
        top_df = df.head(0)

    top_posts = []
    for _, row in top_df.iterrows():
        top_posts.append(
            {
                "caption": first_available(row, ["caption"], ""),
                "image": first_available(row, ["thumbnail_url", "media_url"], ""),
                "permalink": first_available(row, ["permalink"], ""),
                "reach": row[metric_columns["reach"]],
                "views": row[metric_columns["views"]],
                "likes": row[metric_columns["likes"]],
                "comments": row[metric_columns["comments"]],
                "shares": row[metric_columns["shares"]],
                "saved": row[metric_columns["saved"]],
                "interactions": row[metric_columns["interactions"]],
            }
        )

    if total_posts:
        low_df = df.sort_values(
            by=[metric_columns["interactions"], metric_columns["reach"]],
            ascending=True,
        ).head(3)
    else:
        low_df = df.head(0)

    low_posts = []
    for _, row in low_df.iterrows():
        low_posts.append(
            {
                "caption": first_available(row, ["caption"], ""),
                "image": first_available(row, ["thumbnail_url", "media_url"], ""),
                "permalink": first_available(row, ["permalink"], ""),
                "reach": row[metric_columns["reach"]],
                "views": row[metric_columns["views"]],
                "likes": row[metric_columns["likes"]],
                "comments": row[metric_columns["comments"]],
                "shares": row[metric_columns["shares"]],
                "saved": row[metric_columns["saved"]],
                "interactions": row[metric_columns["interactions"]],
            }
        )

    content_type_column = "media_product_type" if "media_product_type" in df.columns else "media_type"
    post_type_counts = (
        df[content_type_column].fillna("UNKNOWN").value_counts().to_dict()
        if total_posts and content_type_column in df.columns
        else {}
    )
    type_summary = (
        df.groupby(content_type_column)
        .agg(
            reach=(metric_columns["reach"], "sum"),
            interactions=(metric_columns["interactions"], "sum"),
        )
        .sort_values("interactions", ascending=False)
        if total_posts and content_type_column in df.columns
        else pd.DataFrame()
    )

    related_months = monthly_context_from_folder(csv_path, account_csv_path)
    if related_months:
        monthly_rows = related_months

    return {
        "source_file": str(csv_path),
        "account_source_file": account.get("source_file", ""),
        "account": account,
        "total_posts": total_posts,
        "total_reach": total_reach,
        "total_views": total_views,
        "total_interactions": total_interactions,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_saved": total_saved,
        "avg_engagement_rate": avg_er,
        "top_posts": top_posts,
        "low_posts": low_posts,
        "monthly_rows": monthly_rows,
        "post_type_counts": post_type_counts,
        "content_type_summary": type_summary.to_dict(orient="index"),
    }


def summarize_month_file(media_csv_path, account_csv_path=None):
    df = pd.read_csv(media_csv_path)
    if df.empty:
        return {}

    metric_columns = {
        "reach": "insight_reach",
        "views": "insight_views",
        "interactions": "insight_total_interactions",
        "likes": "insight_likes",
        "comments": "insight_comments",
        "shares": "insight_shares",
        "saved": "insight_saved",
    }
    for column in metric_columns.values():
        if column not in df.columns:
            df[column] = 0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    period = report_period_from_media_csv(media_csv_path)
    if not period:
        return {}

    account = load_instagram_account(account_csv_path)
    interactions = df[metric_columns["interactions"]].sum()
    reach = df[metric_columns["reach"]].sum()
    return {
        "period": period,
        "name": datetime.strptime(period, "%Y-%m").strftime("%b"),
        "posts": len(df),
        "impr": df[metric_columns["views"]].sum(),
        "reach": reach,
        "likes": df[metric_columns["likes"]].sum(),
        "comm": df[metric_columns["comments"]].sum(),
        "share": df[metric_columns["shares"]].sum(),
        "saved": df[metric_columns["saved"]].sum(),
        "interactions": interactions,
        "er": safe_divide_percent(interactions, reach),
        "followers": account.get("followers_count", 0),
        "follows": account.get("follows_count", 0),
    }


def monthly_context_from_folder(csv_path, account_csv_path=None, max_months=3):
    csv_path = Path(csv_path)
    folder = csv_path.parent
    current_period = report_period_from_media_csv(csv_path)
    if not current_period:
        return []

    media_by_period = latest_files_by_period(
        folder,
        "instagram_media_raw_????-??_*.csv",
        report_period_from_media_csv,
    )
    account_by_period = latest_files_by_period(
        folder,
        "instagram_account_raw_????-??_*.csv",
        report_period_from_account_csv,
    )
    media_by_period[current_period] = csv_path
    if account_csv_path:
        account_period = report_period_from_account_csv(account_csv_path)
        if account_period:
            account_by_period[account_period] = Path(account_csv_path)

    periods = sorted(
        [period for period in media_by_period if period <= current_period],
        reverse=True,
    )[:max_months]
    rows = []
    for period in periods:
        row = summarize_month_file(
            media_by_period[period],
            account_by_period.get(period),
        )
        if not row:
            continue
        rows.append(row)
    for index, row in enumerate(rows):
        followers = number(row.get("followers", 0))
        previous = number(rows[index + 1].get("followers", 0)) if index + 1 < len(rows) else 0
        row["net_growth"] = followers - previous if followers and previous else 0
        row["unfollows"] = "-"
    return rows


def blank_template_defaults():
    """Default untuk placeholder yang belum punya sumber data di prototype CSV."""
    placeholders = [
        "IG_FOL_TARGET_YEAR",
        "IG_FOL_ACTUAL_YEAR",
        "IG_FOL_PCT_YEAR",
        "IG_FOL_TARGET_MONTH",
        "IG_FOL_ACTUAL_MONTH",
        "IG_FOL_PCT_MONTH",
        "IG_REACH_TARGET_YEAR",
        "IG_REACH_PCT_YEAR",
        "IG_REACH_TARGET_MONTH",
        "IG_REACH_PCT_MONTH",
        "IG_TOTAL_FOLLOWERS",
        "AUTO_BENCHMARK_ER",
        "IG_STORIES_COUNT",
        "DEMOGRAPHICS_INSIGHT",
        "AGE_18_24_PCT",
        "AGE_25_34_PCT",
        "AGE_35_44_PCT",
        "AGE_45_PLUS_PCT",
        "TOP_CITY_1",
        "TOP_CITY_1_PCT",
        "TOP_CITY_2",
        "TOP_CITY_2_PCT",
        "TOP_CITY_3",
        "TOP_CITY_3_PCT",
        "GENDER_MALE_PCT",
        "GENDER_FEMALE_PCT",
        "COMP_SELF_GROWTH",
        "COMP_1_NAME",
        "COMP_1_FOL",
        "COMP_1_GROWTH",
        "COMP_1_POSTS",
        "COMP_1_ER",
        "COMP_1_INT",
        "COMP_2_NAME",
        "COMP_2_FOL",
        "COMP_2_GROWTH",
        "COMP_2_POSTS",
        "COMP_2_ER",
        "COMP_2_INT",
        "COMP_3_NAME",
        "COMP_3_FOL",
        "COMP_3_GROWTH",
        "COMP_3_POSTS",
        "COMP_3_ER",
        "COMP_3_INT",
        "FB_KPI_REACH_TARGET",
        "FB_KPI_REACH_PCT",
        "FB_KPI_INT_TARGET",
        "FB_KPI_INT_PCT",
        "FB_TOTAL_REACH",
        "FB_REACH_GROWTH",
        "FB_TOTAL_INT",
        "FB_INT_GROWTH",
        "FB_TOTAL_FOL",
        "YT_INSIGHT_TEXT",
        "TK_INSIGHT_TEXT",
        "YT_TOTAL_SUB",
        "YT_TOTAL_VIEWS",
        "YT_TOTAL_INT",
        "YT_AVG_ER",
        "TK_TOTAL_FOL",
        "TK_TOTAL_VIEWS",
        "TK_TOTAL_LIKES",
        "TK_AVG_ER",
        "WEB_PREV_SESSIONS",
        "WEB_CURR_SESSIONS",
        "WEB_PREV_ORGANIC",
        "WEB_CURR_ORGANIC",
        "WEB_PREV_BOUNCE",
        "WEB_CURR_BOUNCE",
        "WEB_PREV_DUR",
        "WEB_CURR_DUR",
        "SSL_EXPIRY_DATE",
        "DOMAIN_REMAINING_DAYS",
        "WEB_SEO_RECO_TEXT",
        "ADS_REACH_TARGET",
        "ADS_REACH_ACTUAL",
        "ADS_REACH_PCT",
        "ADS_REACH_SPENT",
        "ADS_REACH_REM",
        "ADS_INT_TARGET",
        "ADS_INT_ACTUAL",
        "ADS_INT_PCT",
        "ADS_INT_SPENT",
        "ADS_INT_REM",
        "ADS_YT_TARGET",
        "ADS_YT_ACTUAL",
        "ADS_YT_PCT",
        "ADS_YT_SPENT",
        "ADS_YT_REM",
        "ADS_TK_TARGET",
        "ADS_TK_ACTUAL",
        "ADS_TK_PCT",
        "ADS_TK_SPENT",
        "ADS_TK_REM",
        "ADS_TOTAL_SPENT",
        "ADS_TOTAL_REM",
        "ADS_AVG_CPM",
        "ADS_AVG_CPC",
        "ADS_AVG_CTR",
        "FB_RECOMMENDATION_1",
        "FB_RECOMMENDATION_2",
        "FB_RECOMMENDATION_3",
        "FB_SUMMARY_POINT_1",
        "FB_SUMMARY_POINT_2",
        "FB_SUMMARY_POINT_3",
        "FB_SUMMARY_POINT_4",
        "VID_RECOMMENDATION_1",
        "VID_RECOMMENDATION_2",
        "VID_RECOMMENDATION_3",
        "VID_SUMMARY_POINT_1",
        "VID_SUMMARY_POINT_2",
        "VID_SUMMARY_POINT_3",
        "VID_SUMMARY_POINT_4",
        "LOW_CONTENT_FAILURE_DRIVER",
        "INSIGT_FOLLOWERS_GROWTH_TEXT",
        "IG_SUMMARY_POINT_1",
        "IG_SUMMARY_POINT_2",
        "IG_SUMMARY_POINT_3",
        "IG_SUMMARY_POINT_4",
        "IG_RECOMMENDATION_1",
        "IG_RECOMMENDATION_2",
        "IG_RECOMMENDATION_3",
        "M1_IG_TOTAL_FOLLOWERS",
        "M1_IG_FOLLOWS",
        "M1_IG_UNFOLLOWS",
        "M1_NET_GROWTH",
        "M2_IG_TOTAL_FOLLOWERS",
        "M2_IG_FOLLOWS",
        "M2_IG_UNFOLLOWS",
        "M2_NET_GROWTH",
        "M3_IG_TOTAL_FOLLOWERS",
        "M3_IG_FOLLOWS",
        "M3_IG_UNFOLLOWS",
        "M3_NET_GROWTH",
    ]
    for position in range(1, 4):
        placeholders.extend([
            f"POST_TOP_{position}_TITLE",
            f"POST_TOP_{position}_IMAGE",
            f"POST_TOP_{position}_VIEW",
            f"POST_TOP_{position}_LIKES",
            f"POST_TOP_{position}_COMMENT",
            f"POST_TOP_{position}_SHARE",
            f"POST_TOP_{position}_SAVE",
            f"POST_TOP_{position}_REPOST",
            f"POST_TOP_{position}_MEN",
            f"POST_TOP_{position}_WOMEN",
            f"POST_TOP_{position}_1824",
            f"POST_TOP_{position}_2534",
            f"POST_TOP_{position}_3544",
            f"POST_TOP_{position}_4554",
            f"POST_TOP_{position}_5564",
            f"POST_TOP_{position}_COUNTRY",
            f"POST_LOW_{position}_TITLE",
            f"POST_LOW_{position}_IMAGE",
            f"POST_LOW_{position}_VIEW",
            f"POST_LOW_{position}_LIKES",
            f"POST_LOW_{position}_COMMENT",
            f"POST_LOW_{position}_SHARE",
            f"POST_LOW_{position}_SAVE",
            f"POST_LOW_{position}_REPOST",
            f"POST_LOW_{position}_MEN",
            f"POST_LOW_{position}_WOMEN",
            f"POST_LOW_{position}_1824",
            f"POST_LOW_{position}_2534",
            f"POST_LOW_{position}_3544",
            f"POST_LOW_{position}_4554",
            f"POST_LOW_{position}_5564",
            f"POST_LOW_{position}_COUNTRY",
            f"POST_{position}_VIEW",
            f"POST_{position}_IMAGE",
            f"POST_{position}_LIKES",
            f"POST_{position}_COMMENT",
            f"POST_{position}_SHARE",
            f"POST_{position}_SAVE",
            f"POST_{position}_REPOST",
            f"POST_{position}_MEN",
            f"POST_{position}_WOMEN",
            f"POST_{position}_1824",
            f"POST_{position}_2534",
            f"POST_{position}_3544",
            f"POST_{position}_4554",
            f"POST_{position}_5564",
            f"POST_{position}_COUNTRY",
        ])
    return {f"{{{{{name}}}}}": "-" for name in placeholders}


def compact_kpi_for_ai(kpi, client_name, report_period):
    account = kpi.get("account", {})
    top_posts = []
    for post in kpi.get("top_posts", [])[:3]:
        top_posts.append(
            {
                "caption": str(post.get("caption", ""))[:220],
                "reach": number(post.get("reach", 0)),
                "views": number(post.get("views", 0)),
                "interactions": number(post.get("interactions", 0)),
                "engagement_rate": round(
                    safe_divide_percent(post.get("interactions", 0), post.get("reach", 0)),
                    2,
                ),
            }
        )

    return json_safe({
        "client_name": client_name,
        "report_period": report_period,
        "instagram": {
            "followers_count": account.get("followers_count", 0),
            "total_posts": kpi.get("total_posts", 0),
            "total_reach": kpi.get("total_reach", 0),
            "total_views": kpi.get("total_views", 0),
            "total_interactions": kpi.get("total_interactions", 0),
            "total_likes": kpi.get("total_likes", 0),
            "total_comments": kpi.get("total_comments", 0),
            "total_shares": kpi.get("total_shares", 0),
            "total_saved": kpi.get("total_saved", 0),
            "average_engagement_rate": round(kpi.get("avg_engagement_rate", 0), 2),
            "post_type_counts": kpi.get("post_type_counts", {}),
            "content_type_summary": kpi.get("content_type_summary", {}),
            "monthly_rows": kpi.get("monthly_rows", []),
            "top_posts": top_posts,
        },
    })


def extract_json_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("AI response does not contain a JSON object.")
    return json.loads(match.group(0))


def generate_ai_insights(kpi, client_name, report_period):
    """Minta Gemini menulis insight/recommendation dalam JSON terstruktur."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {}

    import google.generativeai as genai

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    kpi_payload = compact_kpi_for_ai(kpi, client_name, report_period)

    prompt = f"""
You are a senior social media analyst for a digital marketing agency.

Create concise, client-ready insights and recommendations for a Google Slides
social media KPI report. Use ONLY the KPI data below. Do not invent metrics,
benchmarks, competitors, demographics, or paid ads data.

Return ONLY valid JSON with exactly these keys:
{json.dumps(list(AI_PLACEHOLDER_KEYS.keys()), ensure_ascii=False)}

Rules:
- Indonesian language.
- Professional but concise.
- Each value must be a string.
- Each summary/recommendation should fit inside a slide text box.
- Mention concrete numbers when useful.
- If competitor/benchmark data is unavailable, say that it needs additional data.
- Do not use Markdown bullets.

KPI_DATA:
{json.dumps(kpi_payload, ensure_ascii=False, indent=2)}
"""

    response = model.generate_content(prompt)
    parsed = extract_json_object(response.text or "")
    return {
        key: str(parsed.get(key, "")).strip()
        for key in AI_PLACEHOLDER_KEYS
        if str(parsed.get(key, "")).strip()
    }


def apply_ai_insights(mapping, ai_insights):
    for key, placeholder in AI_PLACEHOLDER_KEYS.items():
        value = ai_insights.get(key)
        if value:
            mapping[placeholder] = value
    return mapping


def build_placeholder_mapping(kpi, client_name, report_period, agency_name):
    """Ubah hasil KPI menjadi mapping placeholder Google Slides."""
    top_posts = kpi["top_posts"] + [{} for _ in range(3)]
    low_posts = kpi.get("low_posts", []) + [{} for _ in range(3)]
    content_summary = kpi.get("content_type_summary", {})
    feed = content_summary.get("FEED", {})
    reels = content_summary.get("REELS", {})
    carousel_count = kpi["post_type_counts"].get("CAROUSEL_ALBUM", 0)
    reels_count = kpi["post_type_counts"].get("REELS", 0)
    feed_count = kpi["post_type_counts"].get("FEED", 0)
    static_count = max(feed_count - carousel_count, 0)
    best_content_type = next(iter(content_summary.keys()), "-") if content_summary else "-"
    monthly_rows = kpi.get("monthly_rows", []) + [{} for _ in range(3)]
    account = kpi.get("account", {})
    demographics = account.get("demographics", {})
    account_reach = account.get("insight_reach", 0) or kpi["total_reach"]
    account_views = (
        account.get("insight_views", 0)
        or account.get("insight_impressions", 0)
        or kpi["total_views"]
    )
    account_interactions = account.get("insight_total_interactions", 0) or kpi["total_interactions"]
    followers_count = account.get("followers_count", 0)
    reach_target_month = os.getenv("IG_REACH_TARGET_MONTH", "")
    reach_target_year = os.getenv("IG_REACH_TARGET_YEAR", "")
    follower_target_month = os.getenv("IG_FOL_TARGET_MONTH", "")
    follower_target_year = os.getenv("IG_FOL_TARGET_YEAR", "")

    mapping = blank_template_defaults()
    current_month = monthly_rows[0] if monthly_rows else {}
    previous_month = monthly_rows[1] if len(monthly_rows) > 1 else {}
    reach_growth = number(current_month.get("reach", 0)) - number(previous_month.get("reach", 0))
    interaction_growth = number(current_month.get("interactions", 0)) - number(previous_month.get("interactions", 0))
    follower_growth = number(current_month.get("followers", 0)) - number(previous_month.get("followers", 0))
    mapping.update({
        "{{CLIENT_NAME}}": client_name,
        "{{AGENCY_NAME}}": agency_name,
        "{{REPORT_PERIOD}}": report_period,
        "{{NEXT_REPORT_PERIOD}}": "-",
        "{{TOTAL_REACH}}": fmt_number(kpi["total_reach"]),
        "{{TOTAL_VIEWS}}": fmt_number(kpi["total_views"]),
        "{{TOTAL_INTERACTIONS}}": fmt_number(kpi["total_interactions"]),
        "{{AVG_ENGAGEMENT_RATE}}": fmt_percent(kpi["avg_engagement_rate"]),
        "{{IG_TOTAL_POSTS}}": fmt_number(kpi["total_posts"]),
        "{{IG_TOTAL_FOLLOWERS}}": fmt_number(followers_count) if followers_count else "-",
        "{{IG_TOTAL_REACH}}": fmt_number(account_reach),
        "{{IG_TOTAL_VIEWS}}": fmt_number(account_views),
        "{{IG_TOTAL_INTERACTIONS}}": fmt_number(account_interactions),
        "{{IG_TOTAL_LIKES}}": fmt_number(kpi["total_likes"]),
        "{{IG_TOTAL_COMMENTS}}": fmt_number(kpi["total_comments"]),
        "{{IG_TOTAL_SHARES}}": fmt_number(kpi["total_shares"]),
        "{{IG_TOTAL_SAVED}}": fmt_number(kpi["total_saved"]),
        "{{IG_AVG_ENGAGEMENT_RATE}}": fmt_percent(kpi["avg_engagement_rate"]),
        "{{IG_AVG_ER}}": fmt_percent(kpi["avg_engagement_rate"]),
        "{{IG_FOL_TARGET_YEAR}}": fmt_number(follower_target_year) if follower_target_year else "-",
        "{{IG_FOL_ACTUAL_YEAR}}": fmt_number(followers_count) if followers_count else "-",
        "{{IG_FOL_PCT_YEAR}}": pct(followers_count, follower_target_year),
        "{{IG_FOL_TARGET_MONTH}}": fmt_number(follower_target_month) if follower_target_month else "-",
        "{{IG_FOL_ACTUAL_MONTH}}": fmt_number(followers_count) if followers_count else "-",
        "{{IG_FOL_PCT_MONTH}}": pct(followers_count, follower_target_month),
        "{{IG_REACH_ACTUAL_YEAR}}": fmt_number(account_reach),
        "{{IG_REACH_ACTUAL_MONTH}}": fmt_number(account_reach),
        "{{IG_REACH_TARGET_YEAR}}": fmt_number(reach_target_year) if reach_target_year else "-",
        "{{IG_REACH_TARGET_MONTH}}": fmt_number(reach_target_month) if reach_target_month else "-",
        "{{IG_REACH_PCT_YEAR}}": pct(account_reach, reach_target_year),
        "{{IG_REACH_PCT_MONTH}}": pct(account_reach, reach_target_month),
        "{{IG_REACH_INSIGHT_SUMMARY}}": (
            f"Reach periode ini mencapai {fmt_number(account_reach)} dengan "
            f"{fmt_number(account_interactions)} total interactions dan ER "
            f"{fmt_percent(kpi['avg_engagement_rate'])}."
        ),
        "{{IG_PERFORMANCE_INSIGHT}}": (
            "Instagram menunjukkan total reach "
            f"{fmt_number(kpi['total_reach'])} dan interactions "
            f"{fmt_number(kpi['total_interactions'])} pada periode ini."
        ),
        "{{IG_REELS_COUNT}}": fmt_number(reels_count),
        "{{IG_CAROUSEL_COUNT}}": fmt_number(carousel_count),
        "{{IG_STATIC_COUNT}}": fmt_number(static_count),
        "{{IG_SUMMARY_POINT_1}}": f"Total Instagram reach: {fmt_number(kpi['total_reach'])}.",
        "{{IG_SUMMARY_POINT_2}}": f"Total Instagram interactions: {fmt_number(kpi['total_interactions'])}.",
        "{{IG_SUMMARY_POINT_3}}": f"Average Instagram ER: {fmt_percent(kpi['avg_engagement_rate'])}.",
        "{{IG_SUMMARY_POINT_4}}": f"Best content type: {best_content_type}.",
        "{{IG_RECOMMENDATION_1}}": "Perbanyak format konten dengan interaction tertinggi.",
        "{{IG_RECOMMENDATION_2}}": "Gunakan top content sebagai referensi visual dan caption.",
        "{{IG_RECOMMENDATION_3}}": "Tambahkan target dan benchmark agar achievement bisa dihitung lebih akurat.",
        "{{FB_TOTAL_POSTS}}": "-",
        "{{FB_TOTAL_REACH}}": "-",
        "{{FB_TOTAL_VIEWS}}": "-",
        "{{FB_TOTAL_INTERACTIONS}}": "-",
        "{{FB_TOTAL_REACTIONS}}": "-",
        "{{FB_TOTAL_COMMENTS}}": "-",
        "{{FB_TOTAL_SHARES}}": "-",
        "{{FB_AVG_ENGAGEMENT_RATE}}": "-",
        "{{FB_PERFORMANCE_INSIGHT}}": "Data Facebook belum dimasukkan pada prototype ini.",
        "{{FEED_REACH}}": fmt_number(feed.get("reach", 0)),
        "{{FEED_INTERACTIONS}}": fmt_number(feed.get("interactions", 0)),
        "{{REELS_REACH}}": fmt_number(reels.get("reach", 0)),
        "{{REELS_INTERACTIONS}}": fmt_number(reels.get("interactions", 0)),
        "{{BEST_CONTENT_TYPE}}": best_content_type,
        "{{CONTENT_TYPE_INSIGHT}}": (
            f"Content type dengan performa interaksi tertinggi saat ini adalah {best_content_type}."
        ),
        "{{DEMOGRAPHICS_INSIGHT}}": (
            "Audience demographics berhasil diambil dari Meta API."
            if demographics.get("top_cities")
            or demographics.get("gender_male_pct")
            or demographics.get("age_18_24_pct")
            else "Data demographics belum tersedia dari Meta API pada export ini."
        ),
        "{{AGE_18_24_PCT}}": fmt_number(demographics.get("age_18_24_pct", 0)),
        "{{AGE_25_34_PCT}}": fmt_number(demographics.get("age_25_34_pct", 0)),
        "{{AGE_35_44_PCT}}": fmt_number(demographics.get("age_35_44_pct", 0)),
        "{{AGE_45_PLUS_PCT}}": fmt_number(demographics.get("age_45_plus_pct", 0)),
        "{{GENDER_MALE_PCT}}": fmt_number(demographics.get("gender_male_pct", 0)),
        "{{GENDER_FEMALE_PCT}}": fmt_number(demographics.get("gender_female_pct", 0)),
        "{{CHART_KPI_OVERVIEW}}": "[Chart placeholder: KPI Overview]",
        "{{CHART_CONTENT_TYPE}}": "[Chart placeholder: Content Type Breakdown]",
        "{{EXECUTIVE_SUMMARY}}": (
            f"Selama {report_period}, akun {client_name} menghasilkan "
            f"{fmt_number(kpi['total_reach'])} reach, {fmt_number(kpi['total_views'])} views, "
            f"dan {fmt_number(kpi['total_interactions'])} interactions."
        ),
        "{{KEY_HIGHLIGHT_1}}": f"Total reach: {fmt_number(kpi['total_reach'])}.",
        "{{KEY_HIGHLIGHT_2}}": f"Total views: {fmt_number(kpi['total_views'])}.",
        "{{KEY_HIGHLIGHT_3}}": f"Average engagement rate: {fmt_percent(kpi['avg_engagement_rate'])}.",
        "{{AI_INSIGHT_1}}": "Konten dengan interaction tinggi perlu dijadikan referensi format berikutnya.",
        "{{AI_INSIGHT_2}}": f"{best_content_type} menjadi format konten terkuat pada data saat ini.",
        "{{AI_INSIGHT_3}}": "Perlu monitoring konsisten untuk melihat tren mingguan.",
        "{{AI_RECOMMENDATION_1}}": "Prioritaskan format konten dengan reach dan interaction tertinggi.",
        "{{AI_RECOMMENDATION_2}}": "Gunakan caption dan visual dari top content sebagai benchmark.",
        "{{AI_RECOMMENDATION_3}}": "Tambahkan perbandingan weekly/monthly agar insight lebih tajam.",
        "{{ENGAGEMENT_TREND_TEXT}}": (
            (
                f"{current_month.get('name')} menghasilkan {fmt_number(current_month.get('reach', 0))} reach "
                f"dan {fmt_number(current_month.get('interactions', 0))} interactions. "
                f"Dibanding {previous_month.get('name')}, reach berubah {fmt_number(reach_growth)} "
                f"dan interactions berubah {fmt_number(interaction_growth)}."
            )
            if previous_month
            else (
                f"Data prototype menunjukkan total {fmt_number(kpi['total_posts'])} post dengan "
                f"{fmt_number(kpi['total_reach'])} reach dan {fmt_number(kpi['total_views'])} impressions/views."
            )
        ),
        "{{INSIGT_FOLLOWERS_GROWTH_TEXT}}": (
            (
                f"{current_month.get('name')} memiliki {fmt_number(current_month.get('followers', 0))} followers. "
                f"Dibanding {previous_month.get('name')}, perubahan followers {fmt_number(follower_growth)}."
            )
            if previous_month and current_month.get("followers")
            else f"Total followers saat ini {fmt_number(followers_count)}."
            if followers_count
            else "Data followers growth belum tersedia pada export ini."
        ),
        "{{BENCHMARK_NOTE}}": (
            "Benchmark masih placeholder. Tambahkan benchmark industri setelah sumber data tersedia."
        ),
        "{{TOP_CONTENT_SUCCESS_DRIVER}}": (
            f"Top content dipilih berdasarkan interactions tertinggi. Format terbaik saat ini: {best_content_type}."
        ),
        "{{LOW_CONTENT_FAILURE_DRIVER}}": (
            "Low performing content dipilih dari interaction dan reach terendah. "
            "Evaluasi hook visual, timing, format, dan kejelasan pesan pada konten tersebut."
        ),
        "{{COMPETITOR_STRATEGY_INSIGHT}}": (
            "Data kompetitor belum dimasukkan pada prototype ini."
        ),
        "{{FB_PERFORMANCE_SUMMARY}}": "Data Facebook belum dimasukkan pada prototype ini.",
        "{{SUMMARY_POINT_1}}": f"Total Instagram reach: {fmt_number(kpi['total_reach'])}.",
        "{{SUMMARY_POINT_2}}": f"Total Instagram interactions: {fmt_number(kpi['total_interactions'])}.",
        "{{SUMMARY_POINT_3}}": f"Average Instagram ER: {fmt_percent(kpi['avg_engagement_rate'])}.",
        "{{SUMMARY_POINT_4}}": f"Best content type: {best_content_type}.",
        "{{RECOMMENDATION_1}}": "Perbanyak format konten dengan interaction tertinggi.",
        "{{RECOMMENDATION_2}}": "Gunakan top content sebagai referensi visual dan caption.",
        "{{RECOMMENDATION_3}}": "Tambahkan target dan benchmark agar achievement bisa dihitung lebih akurat.",
    })

    for index in range(3):
        month = monthly_rows[index]
        position = index + 1
        mapping[f"{{{{M{position}_NAME}}}}"] = month.get("name", "-")
        mapping[f"{{{{M{position}_POSTS}}}}"] = fmt_number(month.get("posts", 0))
        mapping[f"{{{{M{position}_IMPR}}}}"] = fmt_number(month.get("impr", 0))
        mapping[f"{{{{M{position}_REACH}}}}"] = fmt_number(month.get("reach", 0))
        mapping[f"{{{{M{position}_IG_TOTAL_FOLLOWERS}}}}"] = (
            fmt_number(month.get("followers", 0)) if month.get("followers") else "-"
        )
        mapping[f"{{{{M{position}_IG_FOLLOWS}}}}"] = (
            fmt_number(month.get("follows", 0)) if month.get("follows") else "-"
        )
        mapping[f"{{{{M{position}_IG_UNFOLLOWS}}}}"] = str(month.get("unfollows", "-"))
        mapping[f"{{{{M{position}_NET_GROWTH}}}}"] = fmt_number(month.get("net_growth", 0))
        mapping[f"{{{{M{position}_LIKES}}}}"] = fmt_number(month.get("likes", 0))
        mapping[f"{{{{M{position}_COMM}}}}"] = fmt_number(month.get("comm", 0))
        mapping[f"{{{{M{position}_SHARE}}}}"] = fmt_number(month.get("share", 0))
        mapping[f"{{{{M{position}_ER}}}}"] = fmt_percent(month.get("er", 0))

    top_cities = demographics.get("top_cities", []) + [{} for _ in range(3)]
    for index in range(3):
        city = top_cities[index]
        position = index + 1
        mapping[f"{{{{TOP_CITY_{position}}}}}"] = city.get("city", "-")
        mapping[f"{{{{TOP_CITY_{position}_PCT}}}}"] = fmt_number(city.get("pct", 0))

    def post_title(post):
        title = str(post.get("caption", "") or "").strip()
        if title:
            return truncate_text(title, 80)
        permalink = str(post.get("permalink", "") or "").strip()
        if permalink:
            return permalink.rstrip("/").split("/")[-1]
        return "-"

    def map_post(prefix, position, post):
        post_er = safe_divide_percent(post.get("interactions", 0), post.get("reach", 0))
        title = post_title(post)
        mapping[f"{{{{{prefix}_{position}_TITLE}}}}"] = title
        mapping[f"{{{{{prefix}_{position}_REACH}}}}"] = fmt_number(post.get("reach", 0))
        mapping[f"{{{{{prefix}_{position}_VIEW}}}}"] = fmt_number(post.get("views", 0))
        mapping[f"{{{{{prefix}_{position}_LIKES}}}}"] = fmt_number(post.get("likes", 0))
        mapping[f"{{{{{prefix}_{position}_COMMENT}}}}"] = fmt_number(post.get("comments", 0))
        mapping[f"{{{{{prefix}_{position}_SHARE}}}}"] = fmt_number(post.get("shares", 0))
        mapping[f"{{{{{prefix}_{position}_SAVE}}}}"] = fmt_number(post.get("saved", 0))
        mapping[f"{{{{{prefix}_{position}_REPOST}}}}"] = fmt_number(post.get("reposts", 0))
        mapping[f"{{{{{prefix}_{position}_ER}}}}"] = fmt_percent(post_er)
        mapping[f"{{{{{prefix}_{position}_MEN}}}}"] = fmt_number(demographics.get("gender_male_pct", 0))
        mapping[f"{{{{{prefix}_{position}_WOMEN}}}}"] = fmt_number(demographics.get("gender_female_pct", 0))
        mapping[f"{{{{{prefix}_{position}_1824}}}}"] = fmt_number(demographics.get("age_18_24_pct", 0))
        mapping[f"{{{{{prefix}_{position}_2534}}}}"] = fmt_number(demographics.get("age_25_34_pct", 0))
        mapping[f"{{{{{prefix}_{position}_3544}}}}"] = fmt_number(demographics.get("age_35_44_pct", 0))
        mapping[f"{{{{{prefix}_{position}_4554}}}}"] = fmt_number(demographics.get("age_45_plus_pct", 0))
        mapping[f"{{{{{prefix}_{position}_5564}}}}"] = "-"
        mapping[f"{{{{{prefix}_{position}_COUNTRY}}}}"] = (
            top_cities[0].get("city", "-") if top_cities else "-"
        )

    for index in range(3):
        post = top_posts[index]
        position = index + 1
        map_post("POST_TOP", position, post)
        mapping[f"{{{{POST_TOP_{position}_IMAGE}}}}"] = post.get("image", "-")
        mapping[f"{{{{TOP_POST_{position}_CAPTION}}}}"] = str(post.get("caption", "-"))[:220]
        mapping[f"{{{{TOP_POST_{position}_IMAGE}}}}"] = post.get("image", "-")
        mapping[f"{{{{TOP_POST_{position}_PERMALINK}}}}"] = post.get("permalink", "-")
        mapping[f"{{{{TOP_POST_{position}_REACH}}}}"] = fmt_number(post.get("reach", 0))
        mapping[f"{{{{TOP_POST_{position}_VIEWS}}}}"] = fmt_number(post.get("views", 0))
        mapping[f"{{{{TOP_POST_{position}_INTERACTIONS}}}}"] = fmt_number(
            post.get("interactions", 0)
        )
        mapping[f"{{{{POST_{position}_TITLE}}}}"] = mapping[f"{{{{POST_TOP_{position}_TITLE}}}}"]
        mapping[f"{{{{POST_{position}_REACH}}}}"] = mapping[f"{{{{POST_TOP_{position}_REACH}}}}"]
        mapping[f"{{{{POST_{position}_IMAGE}}}}"] = mapping[f"{{{{POST_TOP_{position}_IMAGE}}}}"]
        mapping[f"{{{{POST_{position}_VIEW}}}}"] = mapping[f"{{{{POST_TOP_{position}_VIEW}}}}"]
        mapping[f"{{{{POST_{position}_LIKES}}}}"] = mapping[f"{{{{POST_TOP_{position}_LIKES}}}}"]
        mapping[f"{{{{POST_{position}_COMMENT}}}}"] = mapping[f"{{{{POST_TOP_{position}_COMMENT}}}}"]
        mapping[f"{{{{POST_{position}_SHARE}}}}"] = mapping[f"{{{{POST_TOP_{position}_SHARE}}}}"]
        mapping[f"{{{{POST_{position}_SAVE}}}}"] = mapping[f"{{{{POST_TOP_{position}_SAVE}}}}"]
        mapping[f"{{{{POST_{position}_REPOST}}}}"] = mapping[f"{{{{POST_TOP_{position}_REPOST}}}}"]
        mapping[f"{{{{POST_{position}_ER}}}}"] = mapping[f"{{{{POST_TOP_{position}_ER}}}}"]
        mapping[f"{{{{POST_{position}_MEN}}}}"] = mapping[f"{{{{POST_TOP_{position}_MEN}}}}"]
        mapping[f"{{{{POST_{position}_WOMEN}}}}"] = mapping[f"{{{{POST_TOP_{position}_WOMEN}}}}"]
        mapping[f"{{{{POST_{position}_1824}}}}"] = mapping[f"{{{{POST_TOP_{position}_1824}}}}"]
        mapping[f"{{{{POST_{position}_2534}}}}"] = mapping[f"{{{{POST_TOP_{position}_2534}}}}"]
        mapping[f"{{{{POST_{position}_3544}}}}"] = mapping[f"{{{{POST_TOP_{position}_3544}}}}"]
        mapping[f"{{{{POST_{position}_4554}}}}"] = mapping[f"{{{{POST_TOP_{position}_4554}}}}"]
        mapping[f"{{{{POST_{position}_5564}}}}"] = mapping[f"{{{{POST_TOP_{position}_5564}}}}"]
        mapping[f"{{{{POST_{position}_COUNTRY}}}}"] = mapping[f"{{{{POST_TOP_{position}_COUNTRY}}}}"]

    for index in range(3):
        post = low_posts[index]
        position = index + 1
        map_post("POST_LOW", position, post)
        mapping[f"{{{{POST_LOW_{position}_IMAGE}}}}"] = post.get("image", "-")

    return mapping


def copy_template(drive_service, template_id, report_name):
    output_folder_id = os.getenv("GOOGLE_SLIDES_OUTPUT_FOLDER_ID", "").strip()
    body = {"name": report_name}
    body["parents"] = [output_folder_id or "root"]
    copied = (
        drive_service.files()
        .copy(fileId=template_id, body=body)
        .execute()
    )
    return copied["id"]


def image_placeholder_mapping(mapping):
    image_mapping = {}
    for placeholder, value in mapping.items():
        placeholder_name = placeholder.strip("{}")
        image_url = str(value or "").strip()
        if not placeholder_name.endswith("_IMAGE"):
            continue
        if not image_url.startswith(("http://", "https://")):
            continue
        image_mapping[placeholder] = image_url
    return image_mapping


def image_object_ids_by_placeholder(slides_service, presentation_id, image_mapping):
    presentation = (
        slides_service.presentations()
        .get(presentationId=presentation_id)
        .execute()
    )
    matched = {placeholder: [] for placeholder in image_mapping}
    for slide in presentation.get("slides", []):
        for element in slide.get("pageElements", []):
            if "image" not in element:
                continue
            object_id = element.get("objectId")
            alt_text = " ".join(
                str(element.get(field, "") or "")
                for field in ("title", "description")
            )
            for placeholder in image_mapping:
                if placeholder in alt_text and object_id:
                    matched[placeholder].append(object_id)
    return matched


def replace_image_placeholders(slides_service, presentation_id, image_mapping):
    image_object_ids = image_object_ids_by_placeholder(
        slides_service,
        presentation_id,
        image_mapping,
    )

    requests = []
    for placeholder, object_ids in image_object_ids.items():
        for object_id in object_ids:
            requests.append(
                {
                    "replaceImage": {
                        "imageObjectId": object_id,
                        "url": image_mapping[placeholder],
                        "imageReplaceMethod": "CENTER_INSIDE",
                    }
                }
            )

    if requests:
        try:
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests},
            ).execute()
        except Exception as exc:
            print(
                f"Warning: gagal mengganti image object placeholder: {exc}",
                file=sys.stderr,
            )

    for placeholder, image_url in image_mapping.items():
        request = {
            "replaceAllShapesWithImage": {
                "containsText": {
                    "text": placeholder,
                    "matchCase": True,
                },
                "imageUrl": image_url,
                    "replaceMethod": "CENTER_INSIDE",
            }
        }
        try:
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": [request]},
            ).execute()
        except Exception as exc:
            print(
                f"Warning: gagal mengganti image placeholder {placeholder}: {exc}",
                file=sys.stderr,
            )


def replace_placeholders(slides_service, presentation_id, mapping):
    image_placeholders = set(image_placeholder_mapping(mapping))
    requests = []
    for placeholder, value in mapping.items():
        if placeholder in image_placeholders:
            continue
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {
                        "text": placeholder,
                        "matchCase": True,
                    },
                    "replaceText": str(value),
                }
            }
        )

    if not requests:
        return

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()


def get_google_services(credentials_file, token_file, oauth_port):
    auth_mode = os.getenv("GOOGLE_SLIDES_AUTH", "").strip().lower()
    if auth_mode in ("adc", "application_default", "application-default"):
        import google.auth
        from googleapiclient.discovery import build

        credentials, _project_id = google.auth.default(scopes=SCOPES)
        slides_service = build("slides", "v1", credentials=credentials)
        drive_service = build("drive", "v3", credentials=credentials)
        return slides_service, drive_service

    credentials_path = Path(credentials_file)
    try:
        credential_type = json.loads(credentials_path.read_text(encoding="utf-8")).get("type", "")
    except (OSError, json.JSONDecodeError):
        credential_type = ""

    if credential_type == "service_account":
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=SCOPES,
        )
        slides_service = build("slides", "v1", credentials=credentials)
        drive_service = build("drive", "v3", credentials=credentials)
        return slides_service, drive_service

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    credentials = None
    token_path = Path(token_file)

    if token_path.exists() and token_path.stat().st_size > 0:
        credentials = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            credentials = flow.run_local_server(port=oauth_port)

        token_path.write_text(credentials.to_json(), encoding="utf-8")

    slides_service = build("slides", "v1", credentials=credentials)
    drive_service = build("drive", "v3", credentials=credentials)
    return slides_service, drive_service


def parse_args():
    parser = argparse.ArgumentParser(
        description="Contoh generate Google Slides report dari CSV Instagram."
    )
    parser.add_argument("--template", default=default_template())
    parser.add_argument(
        "--data-dir",
        default=str(default_data_dir()),
        help="Folder data root. Default dari DATA_FOLDER atau data.",
    )
    parser.add_argument(
        "--client-id",
        help="Client folder di data/<client-id>/instagram. Kalau kosong, ambil CSV Instagram terbaru dari semua data.",
    )
    parser.add_argument("--csv", help="Path CSV. Kalau kosong, pakai CSV Instagram terbaru.")
    parser.add_argument(
        "--account-csv",
        help="Path CSV account Instagram. Kalau kosong, pakai instagram_account_*.csv terbaru jika ada.",
    )
    parser.add_argument("--client-name", default=None)
    parser.add_argument("--agency-name", default=os.getenv("REPORT_AGENCY_NAME", "MAI"))
    parser.add_argument(
        "--report-period",
        default=os.getenv("REPORT_PERIOD", datetime.now().strftime("%B %Y")),
    )
    parser.add_argument(
        "--credentials",
        default=default_slides_credentials(),
    )
    parser.add_argument("--token", default=os.getenv("GOOGLE_TOKEN_FILE", "token.json"))
    parser.add_argument(
        "--oauth-port",
        type=int,
        default=int(os.getenv("GOOGLE_OAUTH_PORT", "0")),
        help="Port callback OAuth. Default 0 artinya pilih port kosong otomatis.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tampilkan mapping placeholder tanpa membuat Google Slides.",
    )
    parser.add_argument(
        "--no-ai-insights",
        action="store_true",
        help="Matikan AI insight generation dan pakai fallback template.",
    )
    return parser.parse_args()


def generate_slides_report(
    template=None,
    data_dir=None,
    client_id=None,
    csv=None,
    account_csv=None,
    client_name=None,
    agency_name=None,
    report_period=None,
    credentials="credentials.json",
    token="token.json",
    oauth_port=0,
    dry_run=False,
    use_ai_insights=True,
    ai_insights=None,
):
    """Generate Google Slides report dan return hasil sebagai dict.

    Fungsi ini dipakai oleh CLI dan juga bisa dipanggil sebagai tool agentic.
    """
    template_id = extract_presentation_id(template or default_template())
    data_dir = Path(data_dir or default_data_dir())
    resolved_report_period = report_period or os.getenv(
        "REPORT_PERIOD", datetime.now().strftime("%B %Y")
    )
    report_month = report_period_to_month(resolved_report_period)
    csv_path = (
        Path(csv)
        if csv
        else latest_instagram_csv(data_dir, client_id, report_month=report_month)
    )
    account_csv_path = (
        Path(account_csv)
        if account_csv
        else latest_account_csv_for_media(csv_path)
    )

    kpi = calculate_instagram_kpi(csv_path, account_csv_path)
    resolved_client_name = (
        client_name
        or client_from_data_path(csv_path)
        or os.getenv("REPORT_CLIENT_NAME", "Demo Client")
    )
    kpi = merge_sheet_monthly_rows(
        kpi,
        resolved_client_name,
        report_period_from_media_csv(csv_path),
    )
    mapping = build_placeholder_mapping(
        kpi,
        client_name=resolved_client_name,
        report_period=resolved_report_period,
        agency_name=agency_name or os.getenv("REPORT_AGENCY_NAME", "MAI"),
    )
    ai_insights = ai_insights or {}
    if ai_insights:
        apply_ai_insights(mapping, ai_insights)
    elif use_ai_insights:
        try:
            ai_insights = generate_ai_insights(
                kpi,
                client_name=resolved_client_name,
                report_period=resolved_report_period,
            )
            apply_ai_insights(mapping, ai_insights)
        except Exception as exc:
            mapping["{{BENCHMARK_NOTE}}"] = (
                f"AI insight generation failed; using rule-based fallback. Error: {exc}"
            )

    result = {
        "template_id": template_id,
        "csv": str(csv_path),
        "account_csv": str(account_csv_path) if account_csv_path else None,
        "placeholder_count": len(mapping),
        "ai_insights_used": bool(ai_insights),
    }

    if dry_run:
        result["mapping"] = mapping
        return result

    credentials_file = Path(credentials)
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"File OAuth credentials tidak ditemukan: {credentials_file}. "
            "Set GOOGLE_CREDENTIALS_FILE di .env atau taruh credentials.json di folder ini."
        )

    slides_service, drive_service = get_google_services(
        credentials_file,
        token,
        oauth_port,
    )
    report_name = (
        f"SNS Report - {resolved_client_name} - "
        f"{resolved_report_period}"
    )
    presentation_id = copy_template(drive_service, template_id, report_name)
    replace_image_placeholders(
        slides_service,
        presentation_id,
        image_placeholder_mapping(mapping),
    )
    replace_placeholders(slides_service, presentation_id, mapping)

    result["presentation_id"] = presentation_id
    result["presentation_url"] = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    return result


def main():
    load_dotenv()
    args = parse_args()

    result = generate_slides_report(
        template=args.template,
        data_dir=args.data_dir,
        client_id=args.client_id,
        csv=args.csv,
        account_csv=args.account_csv,
        client_name=args.client_name,
        agency_name=args.agency_name,
        report_period=args.report_period,
        credentials=args.credentials,
        token=args.token,
        oauth_port=args.oauth_port,
        dry_run=args.dry_run,
        use_ai_insights=not args.no_ai_insights,
    )

    if args.dry_run:
        print("Template ID:", result["template_id"])
        print("CSV:", result["csv"])
        print("Account CSV:", result["account_csv"] or "-")
        print("AI insights used:", result["ai_insights_used"])
        print(json.dumps(result["mapping"], indent=2, ensure_ascii=False))
        return

    print("Generated presentation:")
    print(result["presentation_url"])


if __name__ == "__main__":
    main()
