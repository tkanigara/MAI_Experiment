from langchain_core.tools import tool
from config.db import get_connection
from datetime import datetime
from decimal import Decimal
import json

def convert_number(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    return value


@tool
def retrieve_kpi(client_code: str,report_date: str,platform: str) -> dict:
    """
    Retrieve KPI Target and KPI Result based on
    client_code, report_date and platform.
    """
    conn = get_connection()
    try:
        report_date = datetime.strptime(report_date,"%Y-%m-%d").date()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    kt.client_id,
                    kt.platform,
                    kt.metric_name,
                    kt.target_month,
                    kt.target_year
                FROM kpi_targets kt

                INNER JOIN clients c
                    ON c.id = kt.client_id

                WHERE
                    c.client_code = %s
                    AND kt.platform = %s
                    AND kt.period_year = EXTRACT(YEAR FROM %s::date)
                    AND kt.period_month = EXTRACT(MONTH FROM %s::date)

                ORDER BY kt.metric_name;
                """,
                (client_code,platform,report_date,report_date,),
            )
            target_rows = cursor.fetchall()
            targets = []
            for row in target_rows:
                targets.append({
                    "client_id": str(row[0]),
                    "platform": row[1],
                    "metric_name": row[2],
                    "target_month": convert_number(row[3]),
                    "target_year": convert_number(row[4]),
                })

            cursor.execute(
                """
                SELECT
                    kr.client_id,
                    kr.platform,
                    kr.metric_name,
                    kr.actual_month,
                    kr.actual_year,
                    kr.target_month,
                    kr.target_year,
                    kr.achievement_month,
                    kr.achievement_year

                FROM kpi_results kr

                INNER JOIN clients c
                    ON c.id = kr.client_id

                INNER JOIN report_periods rp
                    ON rp.id = kr.report_period_id

                WHERE
                    c.client_code = %s
                    AND kr.platform = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s

                ORDER BY kr.metric_name;
                """,
                (client_code,platform,report_date,report_date),
            )

            result_rows = cursor.fetchall()
            results = []
            for row in result_rows:
                results.append({
                    "client_id": str(row[0]),
                    "platform": row[1],
                    "metric_name": row[2],
                    "actual_month": convert_number(row[3]),
                    "actual_year": convert_number(row[4]),
                    "target_month": convert_number(row[5]),
                    "target_year": convert_number(row[6]),
                    "achievement_month": convert_number(row[7]),
                    "achievement_year": convert_number(row[8]),
                })

        return {
            "success": True,
            "client_code": client_code,
            "platform": platform,
            "report_date": report_date.isoformat(),
            "kpi_targets": targets,
            "kpi_results": results,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()

def to_number(value):
    """
    Convert PostgreSQL Decimal values into int/float
    so they can be serialized to JSON.
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)

@tool
def retrieve_socmed_overview(client_code: str,report_date: str):
    """
    Retrieve socmed overview data Result based on
    client_code, report_date.
    """
    conn = get_connection()
    try:
        report_date = datetime.strptime(report_date,"%Y-%m-%d").date()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    so.client_id,
                    so.total_followers,
                    so.follower_growth,
                    so.follower_growth_rate,
                    so.follows,
                    so.unfollows,
                    so.total_posts,
                    so.reels_posts,
                    so.carousel_posts,
                    so.single_posts,
                    so.story_posts,
                    so.total_engagement,
                    so.likes,
                    so.comments,
                    so.shares,
                    so.reach,
                    so.engagement_rate
                FROM instagram_reports so

                INNER JOIN clients c
                    ON c.id = so.client_id

                INNER JOIN report_periods rp
                    ON rp.id = so.report_period_id

                WHERE
                    c.client_code = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s

                LIMIT 1;
                """,
                (client_code, report_date,report_date,),
            )
            row = cursor.fetchone()
            if row is None:
                return {
                    "success": False,
                    "message": "Overview not found."
                }

            return {
                "success": True,
                "overview": {
                    "client_id": str(row[0]),
                    "total_followers": to_number(row[1]),
                    "follower_growth": to_number(row[2]),
                    "follower_growth_rate": to_number(row[3]),
                    "follows": to_number(row[4]),
                    "unfollows": to_number(row[5]),
                    "total_posts": to_number(row[6]),
                    "reels_posts": to_number(row[7]),
                    "carousel_posts": to_number(row[8]),
                    "single_posts": to_number(row[9]),
                    "story_posts": to_number(row[10]),
                    "total_engagement": to_number(row[11]),
                    "likes": to_number(row[12]),
                    "comments": to_number(row[13]),
                    "shares": to_number(row[14]),
                    "reach": to_number(row[15]),
                    "engagement_rate": to_number(row[16]),
                }
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()
@tool
def retrieve_followers_growth(client_code:str, report_date: str):
    """
    Retrieve followers_growth data Result based on
    client_code, report_date.
    """
    conn = get_connection()
    try:
        report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        with conn.cursor() as cursor:
            cursor.execute(
                """ 
                SELECT
                    fg.client_id,
                    fg.report_period_id,
                    fg.total_followers,
                    fg.follower_growth,
                    fg.follower_growth_rate,
                    fg.follows,
                    fg.unfollows
                FROM instagram_reports fg
                INNER JOIN clients c
                    ON c.id = fg.client_id
                INNER JOIN report_periods rp
                    ON rp.id = fg.report_period_id
                WHERE
                    c.client_code = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s
                LIMIT 1;
                """,
                (client_code, report_date, report_date)
            )
            row = cursor.fetchone()
            if row is None :
                return {
                    "succes": False,
                    "message": "Followers Growth Not found"
                }
            return {
                "success": True,
                "report_period_id": str(row[1]),
                "Followers growth": {
                    "client_id": str(row[0]),
                    "total_follower": to_number(row[2]),
                    "follower_growth": to_number(row[3]),
                    "follower_growth_rate": to_number(row[4]),
                    "follows": to_number(row[5]),
                    "unfollows": to_number(row[6])
                }
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()


@tool
def retrieve_followers_growth_history(
    client_code: str,
    current_report_period_id: str,
):
    """
    Retrieve all historical followers growth data before
    the current report period.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    fg.client_id,
                    fg.report_period_id,
                    fg.total_followers,
                    fg.follower_growth,
                    fg.follower_growth_rate,
                    fg.follows,
                    fg.unfollows
                FROM instagram_reports fg
                INNER JOIN clients c
                    ON c.id = fg.client_id
                INNER JOIN report_periods rp
                    ON rp.id = fg.report_period_id
                WHERE
                    c.client_code = %s
                    AND rp.period_end < (
                        SELECT period_end
                        FROM report_periods
                        WHERE id = %s
                    )
                ORDER BY rp.period_end DESC;
                """,
                (
                    client_code,
                    current_report_period_id,
                ),
            )

            rows = cursor.fetchall()

            if rows is None or len(rows) == 0:
                return {
                    "success": False,
                    "message": "Historical Followers Growth not found"
                }

            return {
                "success": True,
                "Followers growth": [
                    {
                        "client_id": str(row[0]),
                        "report_period_id": str(row[1]),
                        "total_follower": to_number(row[2]),
                        "follower_growth": to_number(row[3]),
                        "follower_growth_rate": to_number(row[4]),
                        "follows": to_number(row[5]),
                        "unfollows": to_number(row[6]),
                    }
                    for row in rows
                ]
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()

@tool
def retrieve_engagement_performance(client_code: str, report_date: str):
    """
    Retrieve engagement_performance data Result based on
    client_code, report_date.
    """
    conn = get_connection()
    try:
        report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        with conn.cursor() as cursor:
            cursor.execute(
                """ 
                SELECT
                    ep.client_id,
                    ep.report_period_id,
                    ep.impressions,
                    ep.reach,
                    ep.likes,
                    ep.comments,
                    ep.shares,
                    ep.total_engagement,
                    ep.engagement_rate
                FROM instagram_reports ep
                INNER JOIN clients c
                    ON c.id = ep.client_id
                INNER JOIN report_periods rp
                    ON rp.id = ep.report_period_id
                WHERE
                    c.client_code = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s
                LIMIT 1;
                """,
                (client_code, report_date, report_date)
            )
            row = cursor.fetchone()
            if row is None :
                return {
                    "succes": False,
                    "message": "Followers Growth Not found"
                }
            return {
                "success": True,
                "report_period_id": str(row[1]),
                "Engagement Performance": {
                    "client_id": str(row[0]),
                    "impressions": to_number(row[2]),
                    "reach": to_number(row[3]),
                    "likes": to_number(row[4]),
                    "comments": to_number(row[5]),
                    "shares": to_number(row[6]),
                    "total_engagement": to_number(row[7]),
                    "engagement_rate": to_number(row[8]),
                }
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()

@tool
def retrieve_engagement_performance_history(
    client_code: str,
    current_report_period_id: str,
):
    """
    Retrieve historical engagement performance data before
    the current report period.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ep.client_id,
                    ep.report_period_id,
                    ep.impressions,
                    ep.reach,
                    ep.likes,
                    ep.comments,
                    ep.shares,
                    ep.total_engagement,
                    ep.engagement_rate
                FROM instagram_reports ep
                INNER JOIN clients c
                    ON c.id = ep.client_id
                INNER JOIN report_periods rp
                    ON rp.id = ep.report_period_id
                WHERE
                    c.client_code = %s
                    AND rp.period_end < (
                        SELECT period_end
                        FROM report_periods
                        WHERE id = %s
                    )
                ORDER BY rp.period_end DESC;
                """,
                (
                    client_code,
                    current_report_period_id,
                ),
            )

            rows = cursor.fetchall()

            if not rows:
                return {
                    "success": False,
                    "message": "Historical Engagement Performance not found"
                }

            return {
                "success": True,
                "Engagement Performance": [
                    {
                        "client_id": str(row[0]),
                        "report_period_id": str(row[1]),
                        "impressions": to_number(row[2]),
                        "reach": to_number(row[3]),
                        "likes": to_number(row[4]),
                        "comments": to_number(row[5]),
                        "shares": to_number(row[6]),
                        "total_engagement": to_number(row[7]),
                        "engagement_rate": to_number(row[8]),
                    }
                    for row in rows
                ]
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()
@tool
def retrieve_top_performing_content(client_code: str, report_date: str, platform: str):
    """
    Retrieve Top Performing Content based on
    client_code, report_date, and platform.
    """
    conn = get_connection()
    try:
        report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    cp.client_id,
                    cp.report_period_id,
                    cp.platform,
                    cp.post_id,
                    cp.published_at,
                    cp.caption,
                    cp.permalink,
                    cp.image_url,
                    cp.content_type,
                    cp.content_rank,
                    cp.performance_bucket,
                    cp.likes,
                    cp.comments,
                    cp.shares,
                    cp.saves,
                    cp.reposts,
                    cp.reactions,
                    cp.views,
                    cp.reach,
                    cp.total_engagement,
                    cp.engagement_rate
                FROM social_content_reports cp
                INNER JOIN report_periods rp
                    ON cp.report_period_id = rp.id
                INNER JOIN clients c
                    ON rp.client_id = c.id
                WHERE
                    c.client_code = %s
                    AND cp.platform = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s
                    AND cp.content_rank <= 5
                ORDER BY cp.content_rank;
                """,
                (client_code, platform, report_date, report_date,)
            )

            rows = cursor.fetchall()
            if not rows:
                return {
                    "success": False,
                    "message": "Top Performing Content not found"
                }

            return {
                "success": True,
                "Top Performing Content": [
                    {
                        "client_id": str(row[0]),
                        "report_period_id": str(row[1]),
                        "platform": row[2],
                        "post_id": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "caption": row[5],
                        "permalink": row[6],
                        "image_url": row[7],
                        "content_type": row[8],
                        "content_rank": to_number(row[9]),
                        "performance_bucket": row[10],
                        "likes": to_number(row[11]),
                        "comments": to_number(row[12]),
                        "shares": to_number(row[13]),
                        "saves": to_number(row[14]),
                        "reposts": to_number(row[15]),
                        "reactions": to_number(row[16]),
                        "views": to_number(row[17]),
                        "reach": to_number(row[18]),
                        "total_engagement": to_number(row[19]),
                        "engagement_rate": to_number(row[20]),
                    }
                    for row in rows
                ]
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()

@tool
def retrieve_all_content(client_code: str, report_date: str, platform: str) -> dict:
    """
    Retrieve all content based on client_code, report_date, and platform.
    """
    conn = get_connection()
    try:
        report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    cp.client_id,
                    cp.report_period_id,
                    cp.platform,
                    cp.post_id,
                    cp.published_at,
                    cp.caption,
                    cp.permalink,
                    cp.image_url,
                    cp.content_type,
                    cp.content_rank,
                    cp.performance_bucket,
                    cp.likes,
                    cp.comments,
                    cp.shares,
                    cp.views,
                    cp.reach,
                    cp.total_engagement,
                    cp.engagement_rate
                FROM social_content_reports cp
                JOIN report_periods rp
                    ON cp.report_period_id = rp.id
                JOIN clients c
                    ON rp.client_id = c.id
                WHERE
                    c.client_code = %s
                    AND cp.platform = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s
                ORDER BY cp.published_at DESC;
                """,
                (client_code, platform, report_date, report_date),
            )

            rows = cursor.fetchall()
            if not rows:
                return {
                    "success": False,
                    "message": "Content not found"
                }

            return {
                "success": True,
                "All Content": [
                    {
                        "client_id": str(row[0]),
                        "report_period_id": str(row[1]),
                        "platform": row[2],
                        "post_id": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "caption": row[5],
                        "permalink": row[6],
                        "image_url": row[7],
                        "content_type": row[8],
                        "content_rank": to_number(row[9]),
                        "performance_bucket": row[10],
                        "likes": to_number(row[11]),
                        "comments": to_number(row[12]),
                        "shares": to_number(row[13]),
                        "views": to_number(row[14]),
                        "reach": to_number(row[15]),
                        "total_engagement": to_number(row[16]),
                        "engagement_rate": to_number(row[17]),
                    }
                    for row in rows
                ]
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()

@tool
def retrieve_competitor_analysis(
    client_code: str,
    platform: str,
    report_date: str,
) -> dict:
    """
    Retrieve client metrics and competitor metrics for competitor analysis.
    """

    conn = get_connection()

    try:
        report_date = datetime.strptime(report_date, "%Y-%m-%d").date()

        with conn.cursor() as cursor:

            # ==========================
            # Client Data
            # ==========================
            cursor.execute(
                """
                SELECT
                    ir.client_id,
                    ir.report_period_id,
                    ir.total_followers,
                    ir.follower_growth_rate,
                    ir.total_posts,
                    ir.engagement_rate,
                    ir.total_engagement
                FROM instagram_reports ir
                INNER JOIN clients c
                    ON c.id = ir.client_id
                INNER JOIN report_periods rp
                    ON rp.id = ir.report_period_id
                WHERE
                    c.client_code = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s
                LIMIT 1;
                """,
                (
                    client_code,
                    report_date,
                    report_date,
                ),
            )

            row = cursor.fetchone()

            if row is None:
                return {
                    "success": False,
                    "message": "Client data not found"
                }

            client_data = {
                "client_id": str(row[0]),
                "report_period_id": str(row[1]),
                "total_followers": to_number(row[2]),
                "follower_growth_rate": to_number(row[3]),
                "total_posts": to_number(row[4]),
                "engagement_rate": to_number(row[5]),
                "total_engagement": to_number(row[6]),
            }

            # ==========================
            # Competitor Data
            # ==========================
            cursor.execute(
                """
                SELECT
                    cr.client_id,
                    cr.report_period_id,
                    cr.platform,
                    cr.profile_name,
                    cr.total_followers,
                    cr.follower_growth,
                    cr.follower_growth_rate,
                    cr.total_posts,
                    cr.total_engagement,
                    cr.engagement_rate,
                    cr.reach,
                    cr.impressions
                FROM competitor_profile_reports cr
                INNER JOIN clients c
                    ON c.id = cr.client_id
                INNER JOIN report_periods rp
                    ON rp.id = cr.report_period_id
                WHERE
                    c.client_code = %s
                    AND cr.platform = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s
                ORDER BY
                    cr.total_followers DESC,
                    cr.profile_name ASC;
                """,
                (
                    client_code,
                    platform,
                    report_date,
                    report_date,
                ),
            )

            rows = cursor.fetchall()

            competitors = []

            for row in rows:
                competitors.append(
                    {
                        "client_id": str(row[0]),
                        "report_period_id": str(row[1]),
                        "platform": row[2],
                        "competitor_name": row[3],
                        "total_followers": to_number(row[4]),
                        "follower_growth": to_number(row[5]),
                        "follower_growth_rate": to_number(row[6]),
                        "total_posts": to_number(row[7]),
                        "total_engagement": to_number(row[8]),
                        "engagement_rate": to_number(row[9]),
                        "reach": to_number(row[10]),
                        "impressions": to_number(row[11]),
                    }
                )

            return {
                "success": True,
                "Client": client_data,
                "Competitors": competitors,
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()