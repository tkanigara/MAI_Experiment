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
    "1ZeYnxJOVIjjEbHqa6BJBh30JE3m2SVQuyEcOu4WaiMY/edit?usp=sharing"
)
DEFAULT_DATA_DIR = Path("data/processed")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]


def extract_presentation_id(value):
    """Ambil presentation ID dari URL Google Slides atau ID polos."""
    match = re.search(r"/presentation/d/([^/]+)", value)
    if match:
        return match.group(1)
    return value.strip()


def latest_instagram_csv(data_dir):
    files = sorted(data_dir.glob("instagram_media_*.csv"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"Tidak ada file instagram_media_*.csv di {data_dir}")
    return files[-1]


def latest_optional_csv(data_dir, pattern):
    files = sorted(data_dir.glob(pattern), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def number(value):
    if pd.isna(value):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


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
        "monthly_rows": monthly_rows,
        "post_type_counts": post_type_counts,
        "content_type_summary": type_summary.to_dict(orient="index"),
    }


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
    ]
    return {f"{{{{{name}}}}}": "-" for name in placeholders}


def build_placeholder_mapping(kpi, client_name, report_period, agency_name):
    """Ubah hasil KPI menjadi mapping placeholder Google Slides."""
    top_posts = kpi["top_posts"] + [{} for _ in range(3)]
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
            f"Data prototype menunjukkan total {fmt_number(kpi['total_posts'])} post dengan "
            f"{fmt_number(kpi['total_reach'])} reach dan {fmt_number(kpi['total_views'])} impressions/views."
        ),
        "{{BENCHMARK_NOTE}}": (
            "Benchmark masih placeholder. Tambahkan benchmark industri setelah sumber data tersedia."
        ),
        "{{TOP_CONTENT_SUCCESS_DRIVER}}": (
            f"Top content dipilih berdasarkan interactions tertinggi. Format terbaik saat ini: {best_content_type}."
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

    for index in range(3):
        post = top_posts[index]
        position = index + 1
        title = str(post.get("caption", "-"))[:80]
        post_er = safe_divide_percent(post.get("interactions", 0), post.get("reach", 0))
        mapping[f"{{{{TOP_POST_{position}_CAPTION}}}}"] = str(post.get("caption", "-"))[:220]
        mapping[f"{{{{TOP_POST_{position}_IMAGE}}}}"] = post.get("image", "-")
        mapping[f"{{{{TOP_POST_{position}_PERMALINK}}}}"] = post.get("permalink", "-")
        mapping[f"{{{{TOP_POST_{position}_REACH}}}}"] = fmt_number(post.get("reach", 0))
        mapping[f"{{{{TOP_POST_{position}_VIEWS}}}}"] = fmt_number(post.get("views", 0))
        mapping[f"{{{{TOP_POST_{position}_INTERACTIONS}}}}"] = fmt_number(
            post.get("interactions", 0)
        )
        mapping[f"{{{{POST_{position}_TITLE}}}}"] = title
        mapping[f"{{{{POST_{position}_REACH}}}}"] = fmt_number(post.get("reach", 0))
        mapping[f"{{{{POST_{position}_ER}}}}"] = fmt_percent(post_er)

    return mapping


def copy_template(drive_service, template_id, report_name):
    copied = (
        drive_service.files()
        .copy(fileId=template_id, body={"name": report_name})
        .execute()
    )
    return copied["id"]


def replace_placeholders(slides_service, presentation_id, mapping):
    requests = []
    for placeholder, value in mapping.items():
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
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            credentials = flow.run_local_server(port=oauth_port)

        token_path.write_text(credentials.to_json(), encoding="utf-8")

    slides_service = build("slides", "v1", credentials=credentials)
    drive_service = build("drive", "v3", credentials=credentials)
    return slides_service, drive_service


def parse_args():
    parser = argparse.ArgumentParser(
        description="Contoh generate Google Slides report dari CSV Instagram."
    )
    parser.add_argument("--template", default=DEFAULT_TEMPLATE_URL)
    parser.add_argument("--csv", help="Path CSV. Kalau kosong, pakai CSV Instagram terbaru.")
    parser.add_argument(
        "--account-csv",
        help="Path CSV account Instagram. Kalau kosong, pakai instagram_account_*.csv terbaru jika ada.",
    )
    parser.add_argument("--client-name", default=os.getenv("REPORT_CLIENT_NAME", "Demo Client"))
    parser.add_argument("--agency-name", default=os.getenv("REPORT_AGENCY_NAME", "MAI"))
    parser.add_argument(
        "--report-period",
        default=os.getenv("REPORT_PERIOD", datetime.now().strftime("%B %Y")),
    )
    parser.add_argument("--credentials", default=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"))
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
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    template_id = extract_presentation_id(args.template)
    csv_path = Path(args.csv) if args.csv else latest_instagram_csv(DEFAULT_DATA_DIR)
    account_csv_path = (
        Path(args.account_csv)
        if args.account_csv
        else latest_optional_csv(DEFAULT_DATA_DIR, "instagram_account_*.csv")
    )
    kpi = calculate_instagram_kpi(csv_path, account_csv_path)
    mapping = build_placeholder_mapping(
        kpi,
        client_name=args.client_name,
        report_period=args.report_period,
        agency_name=args.agency_name,
    )

    if args.dry_run:
        print("Template ID:", template_id)
        print("CSV:", csv_path)
        print("Account CSV:", account_csv_path or "-")
        print(json.dumps(mapping, indent=2, ensure_ascii=False))
        return

    credentials_file = Path(args.credentials)
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"File OAuth credentials tidak ditemukan: {credentials_file}. "
            "Set GOOGLE_CREDENTIALS_FILE di .env atau taruh credentials.json di folder ini."
        )

    slides_service, drive_service = get_google_services(
        credentials_file,
        args.token,
        args.oauth_port,
    )
    report_name = f"SNS Report - {args.client_name} - {args.report_period}"
    presentation_id = copy_template(drive_service, template_id, report_name)
    replace_placeholders(slides_service, presentation_id, mapping)

    print("Generated presentation:")
    print(f"https://docs.google.com/presentation/d/{presentation_id}/edit")


if __name__ == "__main__":
    main()
