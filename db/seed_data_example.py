from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_EXAMPLE_DIR = BASE_DIR / "data_example"
PLATFORM_DIRS = {
    "Dunlop_Facebook": "facebook",
    "Dunlop_Instagram": "instagram",
    "Dunlop_Tiktok": "tiktok",
    "Dunlop_Youtube": "youtube",
}
PLATFORM_TABLES = {
    "facebook": "facebook_reports",
    "instagram": "instagram_reports",
    "tiktok": "tiktok_reports",
    "youtube": "youtube_reports",
}


def database_url() -> str:
    load_dotenv(BASE_DIR / ".env")
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://mai_user:mai_password@localhost:5432/mai_socmed_report",
    )


def clean_null(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() == "null":
        return None
    return value


def number(value):
    value = clean_null(value)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {key: clean_null(value) for key, value in row.items() if key}
            for row in csv.DictReader(file, delimiter=";")
        ]


def read_section(folder: Path, filename: str) -> list[dict]:
    return read_csv(folder / filename)


def first_row(folder: Path, filename: str) -> dict:
    rows = read_section(folder, filename)
    return rows[0] if rows else {}


def parse_post_date(value):
    value = clean_null(value)
    if not value:
        return None
    for fmt in ("%d/%m/%Y, %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def date_columns(row: dict) -> list[str]:
    columns = []
    for key in row:
        if not key:
            continue
        try:
            datetime.strptime(key, "%b %d, %Y")
            columns.append(key)
        except ValueError:
            continue
    return columns


def daily_followers(folder: Path) -> list[dict]:
    rows = read_section(folder, "16_Follower.csv")
    if not rows:
        return []
    row = rows[0]
    result = []
    for column in date_columns(row):
        result.append(
            {
                "date": datetime.strptime(column, "%b %d, %Y").date().isoformat(),
                "value": float(number(row.get(column)) or 0),
            }
        )
    return result


def report_period_from_daily(daily_rows: list[dict]) -> tuple[str, str, str]:
    if not daily_rows:
        return "2026-06-01", "2026-06-30", "Jun 2026"
    start = daily_rows[0]["date"]
    end = daily_rows[-1]["date"]
    label = datetime.fromisoformat(start).strftime("%b %Y")
    return start, end, label


def section_rows(folder: Path) -> dict:
    sections = {}
    for path in sorted(folder.glob("*.csv")):
        rows = read_csv(path)
        if rows:
            key = re.sub(r"^\d+_", "", path.stem).lower().replace(" ", "_")
            sections[key] = rows
    return sections


def content_breakdown(folder: Path) -> dict:
    posts = read_section(folder, "22_Number of posts.csv")
    engagement = read_section(folder, "23_Reactions, Comments & Shares.csv")
    breakdown = {}
    for row in posts:
        key = clean_null(row.get("Profile")) or clean_null(row.get("Profile-ID"))
        if key:
            breakdown.setdefault(key, {})["posts"] = float(number(row.get("Number of posts")) or 0)
    for row in engagement:
        key = clean_null(row.get("Profile")) or clean_null(row.get("Profile-ID"))
        if key:
            breakdown.setdefault(key, {})["engagement"] = float(
                number(row.get("Reactions, Comments & Shares")) or 0
            )
    return breakdown


def best_times(folder: Path) -> list[dict]:
    rows = read_section(folder, "12_Best Times To Post.csv")
    return [
        {
            "slot": row.get("Profile"),
            "posts": float(number(row.get("Number of posts")) or 0),
            "engagement": float(number(row.get("Reactions, Comments & Shares")) or 0),
            "raw": row,
        }
        for row in rows
    ]


def post_payload(row: dict, rank: int, bucket: str) -> dict:
    return {
        "rank": rank,
        "bucket": bucket,
        "post_id": row.get("Post-ID"),
        "published_at": parse_post_date(row.get("Date")).isoformat()
        if parse_post_date(row.get("Date"))
        else None,
        "caption": row.get("Message"),
        "permalink": row.get("Link"),
        "image_url": row.get("Image Link"),
        "likes": float(number(row.get("Number of Likes")) or 0),
        "comments": float(number(row.get("Number of comments")) or 0),
        "total_engagement": float(number(row.get("Reactions, Comments & Shares")) or 0),
        "engagement_rate": float(number(row.get("Post interaction rate")) or 0),
        "reach_per_post": float(number(row.get("Reach per post")) or 0),
        "interactions_per_impression": float(
            number(row.get("Interactions per impression/view")) or 0
        ),
        "negative_comment_share": float(
            number(row.get("Post comments negative sentiment share")) or 0
        ),
        "raw": row,
    }


def post_lists(folder: Path) -> tuple[list[dict], list[dict]]:
    rows = read_section(folder, "11_New 100 Posts Overview.csv")
    rows = sorted(
        rows,
        key=lambda row: number(row.get("Reactions, Comments & Shares")) or Decimal("0"),
        reverse=True,
    )
    top_posts = [post_payload(row, index + 1, "top") for index, row in enumerate(rows[:10])]
    low_source = list(reversed(rows[-10:])) if rows else []
    low_posts = [post_payload(row, index + 1, "low") for index, row in enumerate(low_source)]
    return top_posts, low_posts


def top_level_summary(folder: Path) -> dict:
    likes = first_row(folder, "1_Number of Likes.csv")
    follower = first_row(folder, "2_Follower.csv")
    follower_growth = first_row(folder, "3_Follower Growth (in %).csv")
    posts_per_day = first_row(folder, "4_Posts per day.csv")
    post_interaction = first_row(folder, "5_Post interaction rate.csv")
    engagement = first_row(folder, "6_Engagement.csv")
    ppi = first_row(folder, "7_Page Performance Index.csv")
    return {
        "profile_name": likes.get("Profile"),
        "social_network": likes.get("Social network"),
        "source_profile_id": likes.get("Profile-ID"),
        "profile_url": likes.get("Link"),
        "image_url": likes.get("Image Link"),
        "likes": number(likes.get("Number of Likes")),
        "comments": number(likes.get("Number of comments")),
        "total_engagement": number(likes.get("Reactions, Comments & Shares")),
        "post_interaction_rate": number(post_interaction.get("Post interaction rate (None)"))
        or number(likes.get("Post interaction rate")),
        "reach_per_post": number(likes.get("Reach per post")),
        "interactions_per_impression": number(likes.get("Interactions per impression/view")),
        "total_followers": number(follower.get("Follower (None)")),
        "follower_growth_rate": number(
            follower_growth.get("Follower Growth (in %) (None)")
        ),
        "posts_per_day": number(posts_per_day.get("Posts per day (None)")),
        "engagement_rate": number(engagement.get("Engagement (None)")),
        "page_performance_index": number(ppi.get("Page Performance Index (None)")),
    }


def total_posts(folder: Path) -> Decimal | None:
    rows = read_section(folder, "22_Number of posts.csv")
    values = [number(row.get("Number of posts")) for row in rows]
    values = [value for value in values if value is not None]
    return sum(values, Decimal("0")) if values else None


def insert_scalar(conn, sql: str, params: dict, key: str = "id"):
    return conn.execute(text(sql), params).mappings().one()[key]


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def seed_platform(conn, client_id, period_id, folder: Path, platform: str):
    summary = top_level_summary(folder)
    daily_rows = daily_followers(folder)
    top_posts, low_posts = post_lists(folder)
    sections = section_rows(folder)
    source_profile_id = summary["source_profile_id"] or f"{platform}_{summary['profile_name']}"

    profile_id = insert_scalar(
        conn,
        """
        INSERT INTO client_social_profiles (
            client_id, platform, source, source_profile_id, profile_name,
            profile_url, image_url, raw_profile
        )
        VALUES (
            :client_id, :platform, 'fanpage_karma', :source_profile_id,
            :profile_name, :profile_url, :image_url, CAST(:raw_profile AS jsonb)
        )
        ON CONFLICT (source, platform, source_profile_id)
        DO UPDATE SET
            profile_name = EXCLUDED.profile_name,
            profile_url = EXCLUDED.profile_url,
            image_url = EXCLUDED.image_url,
            raw_profile = EXCLUDED.raw_profile,
            updated_at = now()
        RETURNING id
        """,
        {
            "client_id": client_id,
            "platform": platform,
            "source_profile_id": source_profile_id,
            "profile_name": summary["profile_name"],
            "profile_url": summary["profile_url"],
            "image_url": summary["image_url"],
            "raw_profile": json_dumps(summary),
        },
    )

    conn.execute(
        text(
            """
            DELETE FROM raw_api_responses
            WHERE client_id = :client_id
              AND profile_id = :profile_id
              AND platform = :platform
              AND source = 'fanpage_karma'
            """
        ),
        {
            "client_id": client_id,
            "profile_id": profile_id,
            "platform": platform,
        },
    )

    for endpoint, rows in sections.items():
        conn.execute(
            text(
                """
                INSERT INTO raw_api_responses (
                    client_id, profile_id, source, platform, endpoint, response
                )
                VALUES (
                    :client_id, :profile_id, 'fanpage_karma', :platform,
                    :endpoint, CAST(:response AS jsonb)
                )
                """
            ),
            {
                "client_id": client_id,
                "profile_id": profile_id,
                "platform": platform,
                "endpoint": endpoint,
                "response": json_dumps(rows),
            },
        )

    report_table = PLATFORM_TABLES[platform]
    total_post_count = total_posts(folder)
    approx_reach = None
    if summary["reach_per_post"] is not None and total_post_count is not None:
        approx_reach = summary["reach_per_post"] * total_post_count

    common_params = {
        "client_id": client_id,
        "profile_id": profile_id,
        "period_id": period_id,
        "total_followers": summary["total_followers"],
        "follower_growth_rate": summary["follower_growth_rate"],
        "reach": approx_reach,
        "total_engagement": summary["total_engagement"],
        "engagement_rate": summary["engagement_rate"],
        "likes": summary["likes"],
        "comments": summary["comments"],
        "total_posts": total_post_count,
        "posts_per_day": summary["posts_per_day"],
        "post_interaction_rate": summary["post_interaction_rate"],
        "page_performance_index": summary["page_performance_index"],
        "daily_followers": json_dumps(daily_rows),
        "daily_engagement": json_dumps([]),
        "top_posts": json_dumps(top_posts),
        "low_posts": json_dumps(low_posts),
        "top_hashtags": json_dumps([]),
        "top_words": json_dumps([]),
        "best_times": json_dumps(best_times(folder)),
        "content_breakdown": json_dumps(content_breakdown(folder)),
        "raw_sections": json_dumps(sections),
    }

    if platform == "youtube":
        columns = [
            "client_id",
            "profile_id",
            "report_period_id",
            "total_subscribers",
            "subscriber_growth_rate",
            "total_views",
            "total_engagement",
            "engagement_rate",
            "likes",
            "comments",
            "total_posts",
            "posts_per_day",
            "post_interaction_rate",
            "page_performance_index",
            "daily_subscribers",
            "daily_views",
            "daily_engagement",
            "top_posts",
            "low_posts",
            "top_hashtags",
            "top_words",
            "best_times_to_post",
            "raw_sections",
        ]
        params_by_column = {
            "client_id": "client_id",
            "profile_id": "profile_id",
            "report_period_id": "period_id",
            "total_subscribers": "total_followers",
            "subscriber_growth_rate": "follower_growth_rate",
            "total_views": "reach",
            "daily_subscribers": "daily_followers",
            "daily_views": "daily_engagement",
            "best_times_to_post": "best_times",
        }
    else:
        columns = [
            "client_id",
            "profile_id",
            "report_period_id",
            "total_followers",
            "follower_growth_rate",
            "reach",
            "total_engagement",
            "engagement_rate",
            "likes",
            "comments",
            "total_posts",
            "posts_per_day",
            "post_interaction_rate",
            "page_performance_index",
            "daily_followers",
            "daily_engagement",
            "top_posts",
            "low_posts",
            "top_hashtags",
            "top_words",
            "best_times_to_post",
            "content_type_breakdown",
            "raw_sections",
        ]
        params_by_column = {
            "client_id": "client_id",
            "profile_id": "profile_id",
            "report_period_id": "period_id",
            "best_times_to_post": "best_times",
            "content_type_breakdown": "content_breakdown",
        }
    json_columns = {
        "daily_followers",
        "daily_engagement",
        "top_posts",
        "low_posts",
        "top_hashtags",
        "top_words",
        "best_times_to_post",
        "content_type_breakdown",
        "raw_sections",
    }
    insert_values = []
    for column in columns:
        param = params_by_column.get(column, column)
        if column in json_columns:
            insert_values.append(f"CAST(:{param} AS jsonb)")
        else:
            insert_values.append(f":{param}")
    assignments = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in columns
        if column not in {"client_id", "profile_id", "report_period_id"}
    )
    report_id = insert_scalar(
        conn,
        f"""
        INSERT INTO {report_table} ({", ".join(columns)})
        VALUES ({", ".join(insert_values)})
        ON CONFLICT (client_id, profile_id, report_period_id)
        DO UPDATE SET {assignments}, updated_at = now()
        RETURNING id
        """,
        common_params,
    )

    kpis = {
        "followers": summary["follower_growth_rate"],
        "engagement": summary["total_engagement"],
        "reach": approx_reach,
    }
    if platform == "youtube":
        kpis = {
            "subscribers": summary["follower_growth_rate"],
            "engagement": summary["total_engagement"],
            "views": approx_reach,
        }
    for metric_name, actual_month in kpis.items():
        conn.execute(
            text(
                """
                INSERT INTO kpi_results (
                    client_id, profile_id, report_period_id, platform, metric_name,
                    actual_month, unit, source_report_table, source_report_id, metadata
                )
                VALUES (
                    :client_id, :profile_id, :period_id, :platform, :metric_name,
                    :actual_month, :unit, :source_report_table, :source_report_id,
                    CAST(:metadata AS jsonb)
                )
                ON CONFLICT (client_id, platform, report_period_id, metric_name)
                DO UPDATE SET
                    profile_id = EXCLUDED.profile_id,
                    actual_month = EXCLUDED.actual_month,
                    unit = EXCLUDED.unit,
                    source_report_table = EXCLUDED.source_report_table,
                    source_report_id = EXCLUDED.source_report_id,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                """
            ),
            {
                "client_id": client_id,
                "profile_id": profile_id,
                "period_id": period_id,
                "platform": platform,
                "metric_name": metric_name,
                "actual_month": actual_month,
                "unit": "count",
                "source_report_table": report_table,
                "source_report_id": report_id,
                "metadata": json_dumps({"seed_source": str(folder.name)}),
            },
        )

    return platform, summary["profile_name"], len(top_posts)


def main():
    engine = create_engine(database_url())
    with engine.begin() as conn:
        client_id = insert_scalar(
            conn,
            """
            INSERT INTO clients (
                client_code, client_name, industry, has_instagram,
                has_facebook, has_tiktok, has_youtube, metadata
            )
            VALUES (
                'dunlop', 'Dunlop Indonesia', 'Automotive',
                TRUE, TRUE, TRUE, TRUE, CAST(:metadata AS jsonb)
            )
            ON CONFLICT (client_code)
            DO UPDATE SET
                client_name = EXCLUDED.client_name,
                industry = EXCLUDED.industry,
                has_instagram = EXCLUDED.has_instagram,
                has_facebook = EXCLUDED.has_facebook,
                has_tiktok = EXCLUDED.has_tiktok,
                has_youtube = EXCLUDED.has_youtube,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            RETURNING id
            """,
            {"metadata": json_dumps({"seed_source": "data_example"})},
        )

        first_daily = []
        for folder_name in PLATFORM_DIRS:
            first_daily = daily_followers(DATA_EXAMPLE_DIR / folder_name)
            if first_daily:
                break
        start, end, label = report_period_from_daily(first_daily)
        period_id = insert_scalar(
            conn,
            """
            INSERT INTO report_periods (
                client_id, period_start, period_end, period_label
            )
            VALUES (:client_id, :period_start, :period_end, :period_label)
            ON CONFLICT (client_id, period_start, period_end)
            DO UPDATE SET period_label = EXCLUDED.period_label
            RETURNING id
            """,
            {
                "client_id": client_id,
                "period_start": start,
                "period_end": end,
                "period_label": label,
            },
        )

        seeded = []
        for folder_name, platform in PLATFORM_DIRS.items():
            folder = DATA_EXAMPLE_DIR / folder_name
            if folder.exists():
                seeded.append(seed_platform(conn, client_id, period_id, folder, platform))

    print("Seeded data_example into PostgreSQL:")
    for platform, profile_name, top_count in seeded:
        print(f"- {platform}: {profile_name} ({top_count} top posts)")


if __name__ == "__main__":
    main()
