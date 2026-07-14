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

                INNER JOIN report_periods rp
                    ON rp.id = kt.report_period_id

                WHERE
                    c.client_code = %s
                    AND kt.platform = %s
                    AND rp.period_start <= %s
                    AND rp.period_end >= %s

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
def retrieve_socmed_overview(client_code: str,report_date: str,):
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
                    so.follows,
                    so.video_posts,
                    so.total_engagement,
                    so.likes,
                    so.comments,
                    so.shares,
                    so.reach,
                    so.engagement_rate,
                    so.total_views
                FROM tiktok_reports so

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
                    "follows": to_number(row[2]),
                    "video_posts": to_number(row[3]),
                    "total_engagement": to_number(row[4]),
                    "likes": to_number(row[5]),
                    "comments": to_number(row[6]),
                    "shares": to_number(row[7]),
                    "reach": to_number(row[8]),
                    "engagement_rate": to_number(row[9]),
                    "views": to_number(row[10])
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
                    fg.total_followers,
                    fg.follower_growth,
                    fg.follows
                FROM tiktok_reports fg
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
                "Followers growth": {
                    "client_id": str(row[0]),
                    "total_follower": to_number(row[1]),
                    "follower_growth": to_number(row[2]),
                    "follows": to_number(row[3]),
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
                    ep.likes,
                    ep.comments,
                    ep.shares,
                    ep.total_engagement,
                    ep.engagement_rate,
                    ep.total_views
                FROM tiktok_reports ep
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
                "Engagement Performance": {
                    "client_id": str(row[0]),
                    "likes": to_number(row[1]),
                    "comments": to_number(row[2]),
                    "shares": to_number(row[3]),
                    "total_engagement":to_number(row[4]),
                    "engagement_rate":to_number(row[5]),
                    "views": to_number(row[6])
                }
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()