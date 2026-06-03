import json
from pathlib import Path

import pandas as pd


def number(value):
    if value is None:
        return 0.0
    try:
        if pd.isna(value):
            return 0.0
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def json_safe(value):
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


def safe_divide(numerator, denominator):
    denominator = number(denominator)
    if not denominator:
        return 0.0
    return number(numerator) / denominator


def safe_divide_percent(numerator, denominator):
    return safe_divide(numerator, denominator) * 100


def read_csv_rows(path):
    csv_path = Path(path)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def first_available(row, columns, default=""):
    for column in columns:
        if column in row and not pd.isna(row[column]):
            return row[column]
    return default


def normalize_type(value):
    value = str(value or "").strip().upper()
    return value or "UNKNOWN"


def metric_column(df, name, fallbacks=None):
    candidates = [name] + list(fallbacks or [])
    for column in candidates:
        if column in df.columns:
            return column
    df[name] = 0
    return name


def load_instagram_account(account_csv_path=None):
    if not account_csv_path:
        return {}

    df = read_csv_rows(account_csv_path)
    if df.empty:
        return {}

    row = df.iloc[-1].to_dict()
    return json_safe(
        {
            "source_file": str(account_csv_path),
            "id": row.get("id", ""),
            "username": row.get("username", ""),
            "name": row.get("name", ""),
            "followers_count": number(row.get("followers_count", 0)),
            "follows_count": number(row.get("follows_count", 0)),
            "media_count": number(row.get("media_count", 0)),
            "insight_reach": number(row.get("insight_reach", 0)),
            "insight_views": number(row.get("insight_views", 0)),
            "insight_impressions": number(row.get("insight_impressions", 0)),
            "insight_profile_views": number(row.get("insight_profile_views", 0)),
            "insight_accounts_engaged": number(row.get("insight_accounts_engaged", 0)),
            "insight_total_interactions": number(row.get("insight_total_interactions", 0)),
        }
    )


def summarize_content_type(df, type_column, metric_columns):
    if df.empty or type_column not in df.columns:
        return {}

    grouped = (
        df.groupby(type_column)
        .agg(
            posts=("id", "count") if "id" in df.columns else (metric_columns["reach"], "count"),
            reach=(metric_columns["reach"], "sum"),
            views=(metric_columns["views"], "sum"),
            likes=(metric_columns["likes"], "sum"),
            comments=(metric_columns["comments"], "sum"),
            shares=(metric_columns["shares"], "sum"),
            saved=(metric_columns["saved"], "sum"),
            total_interactions=(metric_columns["interactions"], "sum"),
        )
        .reset_index()
    )
    grouped["avg_engagement_rate"] = grouped.apply(
        lambda row: safe_divide_percent(row["total_interactions"], row["reach"]),
        axis=1,
    )

    result = {}
    for _, row in grouped.iterrows():
        key = normalize_type(row[type_column])
        result[key] = json_safe(row.drop(labels=[type_column]).to_dict())
    return result


def calculate_instagram_kpi(media_csv_path, account_csv_path=None):
    df = read_csv_rows(media_csv_path)
    account = load_instagram_account(account_csv_path)

    if df.empty:
        return {
            "platform": "instagram",
            "source_file": str(media_csv_path),
            "account_source_file": str(account_csv_path or ""),
            "account": account,
            "total_posts": 0,
            "total_reach": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "total_saved": 0,
            "total_interactions": 0,
            "avg_engagement_rate": 0,
            "top_3_content": [],
            "best_content_type": "",
            "feed_stats": {},
            "reels_stats": {},
            "content_type_stats": {},
            "monthly_stats": [],
        }

    type_column = "media_product_type" if "media_product_type" in df.columns else "media_type"
    if type_column in df.columns:
        df[type_column] = df[type_column].apply(normalize_type)

    metric_columns = {
        "reach": metric_column(df, "insight_reach"),
        "views": metric_column(df, "insight_views", ["insight_impressions", "insight_video_views"]),
        "likes": metric_column(df, "insight_likes", ["like_count"]),
        "comments": metric_column(df, "insight_comments", ["comments_count"]),
        "shares": metric_column(df, "insight_shares"),
        "saved": metric_column(df, "insight_saved", ["insight_saves"]),
        "interactions": metric_column(df, "insight_total_interactions", ["insight_engagement"]),
    }
    for column in set(metric_columns.values()):
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    interaction_parts = [
        metric_columns["likes"],
        metric_columns["comments"],
        metric_columns["shares"],
        metric_columns["saved"],
    ]
    if df[metric_columns["interactions"]].sum() == 0:
        df[metric_columns["interactions"]] = df[interaction_parts].sum(axis=1)

    df["_engagement_rate"] = df.apply(
        lambda row: safe_divide_percent(row[metric_columns["interactions"]], row[metric_columns["reach"]]),
        axis=1,
    )

    totals = {
        "total_posts": int(len(df)),
        "total_reach": number(df[metric_columns["reach"]].sum()),
        "total_views": number(df[metric_columns["views"]].sum()),
        "total_likes": number(df[metric_columns["likes"]].sum()),
        "total_comments": number(df[metric_columns["comments"]].sum()),
        "total_shares": number(df[metric_columns["shares"]].sum()),
        "total_saved": number(df[metric_columns["saved"]].sum()),
        "total_interactions": number(df[metric_columns["interactions"]].sum()),
    }
    totals["avg_engagement_rate"] = safe_divide_percent(
        totals["total_interactions"],
        totals["total_reach"],
    )

    top_df = df.sort_values(
        by=[metric_columns["interactions"], metric_columns["reach"]],
        ascending=False,
    ).head(3)
    top_content = []
    for _, row in top_df.iterrows():
        top_content.append(
            json_safe(
                {
                    "id": row.get("id", ""),
                    "timestamp": row.get("timestamp", ""),
                    "caption": str(first_available(row, ["caption"], ""))[:500],
                    "media_type": row.get("media_type", ""),
                    "media_product_type": row.get("media_product_type", ""),
                    "permalink": row.get("permalink", ""),
                    "thumbnail_url": first_available(row, ["thumbnail_url", "media_url"], ""),
                    "reach": row[metric_columns["reach"]],
                    "views": row[metric_columns["views"]],
                    "likes": row[metric_columns["likes"]],
                    "comments": row[metric_columns["comments"]],
                    "shares": row[metric_columns["shares"]],
                    "saved": row[metric_columns["saved"]],
                    "total_interactions": row[metric_columns["interactions"]],
                    "engagement_rate": row["_engagement_rate"],
                }
            )
        )

    content_type_stats = summarize_content_type(df, type_column, metric_columns)
    best_content_type = ""
    if content_type_stats:
        best_content_type = max(
            content_type_stats.items(),
            key=lambda item: (number(item[1].get("total_interactions")), number(item[1].get("reach"))),
        )[0]

    monthly_stats = []
    if "timestamp" in df.columns:
        periods = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df["_period"] = periods.dt.tz_convert(None).dt.to_period("M")
        monthly_df = (
            df.dropna(subset=["_period"])
            .groupby("_period")
            .agg(
                posts=("id", "count") if "id" in df.columns else (metric_columns["reach"], "count"),
                reach=(metric_columns["reach"], "sum"),
                views=(metric_columns["views"], "sum"),
                interactions=(metric_columns["interactions"], "sum"),
            )
            .tail(6)
        )
        for period, row in monthly_df.iterrows():
            monthly_stats.append(
                json_safe(
                    {
                        "period": str(period),
                        "posts": row["posts"],
                        "reach": row["reach"],
                        "views": row["views"],
                        "interactions": row["interactions"],
                        "engagement_rate": safe_divide_percent(row["interactions"], row["reach"]),
                    }
                )
            )

    result = {
        "platform": "instagram",
        "source_file": str(media_csv_path),
        "account_source_file": str(account_csv_path or ""),
        "account": account,
        **totals,
        "top_3_content": top_content,
        "top_posts": top_content,
        "best_content_type": best_content_type,
        "feed_stats": content_type_stats.get("FEED", {}),
        "reels_stats": content_type_stats.get("REELS", {}),
        "content_type_stats": content_type_stats,
        "content_type_summary": content_type_stats,
        "post_type_counts": (
            {str(key): int(value) for key, value in df[type_column].value_counts().to_dict().items()}
            if type_column in df.columns
            else {}
        ),
        "monthly_stats": monthly_stats,
        "monthly_rows": monthly_stats,
    }
    return json_safe(result)


def latest_csv(data_dir, pattern):
    files = sorted(Path(data_dir).glob(pattern), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def dumps_compact(value):
    return json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)
