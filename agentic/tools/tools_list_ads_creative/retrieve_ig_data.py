from langchain_core.tools import tool
from agentic.config.db import get_connection
from decimal import Decimal


def to_number(value):
    """
    Convert PostgreSQL Decimal values into int/float
    so they can be serialized to JSON.
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)

    return value


def calculate_percentage(numerator, denominator):
    """
    Calculate percentage safely.
    """
    if denominator in (None, 0):
        return 0

    return round((numerator / denominator) * 100, 2)


@tool
def performance_overview(
    client_code: str,
    period_id: str,
    objective: str
) -> dict:
    """
    Retrieve ad-level performance overview based on
    client code, reporting period, and objective.
    """

    conn = get_connection()

    try:
        objective = objective.lower().strip()

        objective_mapping = {
            "reach": "reach",
            "engagement": "post_engagement",
            "views": "video_view",
            "link clicks": "link_click",
            "leads": "lead",
        }

        result_type = objective_mapping.get(objective)

        if result_type is None:
            return {
                "success": False,
                "message": f"Objective '{objective}' is not available."
            }

        with conn.cursor() as cursor:

            # ==========================================================
            # 1. Retrieve AD LEVEL performance
            # ==========================================================

            cursor.execute(
                """
                SELECT
                    ap.client_id,
                    ap.ad_name,
                    ap.reach,
                    ap.impressions,
                    ap.link_clicks,
                    ap.post_engagements,
                    ap.spend
                FROM meta_ads_ad_performance ap

                INNER JOIN clients c
                    ON c.id = ap.client_id

                INNER JOIN meta_ads_report_periods rp
                    ON rp.id = ap.meta_ads_report_period_id

                WHERE
                    c.client_code = %s
                    AND rp.period_start = %s
                """,
                (
                    client_code,
                    period_id,
                ),
            )

            rows = cursor.fetchall()

            print("\n========================================")
            print("[DEBUG] PERFORMANCE OVERVIEW")
            print("========================================")
            print(f"[DEBUG] client_code : {client_code}")
            print(f"[DEBUG] period_id   : {period_id}")
            print(f"[DEBUG] objective   : {objective}")
            print(f"[DEBUG] result_type : {result_type}")
            print(f"[DEBUG] rows        : {len(rows)}")

            if not rows:
                return {
                    "success": False,
                    "message": "Performance overview not found."
                }

            # ==========================================================
            # 2. Aggregate by AD NAME
            # ==========================================================

            ad_data = {}

            for row in rows:

                client_id = row[0]
                ad_name = row[1]

                reach = to_number(row[2]) or 0
                impressions = to_number(row[3]) or 0
                link_clicks = to_number(row[4]) or 0
                engagements = to_number(row[5]) or 0
                spend = to_number(row[6]) or 0

                if ad_name not in ad_data:
                    ad_data[ad_name] = {
                        "ad_name": ad_name,
                        "reach": 0,
                        "impressions": 0,
                        "engagements": 0,
                        "link_clicks": 0,
                        "spend": 0,
                    }

                ad_data[ad_name]["reach"] += reach
                ad_data[ad_name]["impressions"] += impressions
                ad_data[ad_name]["engagements"] += engagements
                ad_data[ad_name]["link_clicks"] += link_clicks
                ad_data[ad_name]["spend"] += spend

            # ==========================================================
            # 3. Calculate derived metrics
            # ==========================================================

            ads = []

            for ad in ad_data.values():

                reach = ad["reach"]
                impressions = ad["impressions"]
                engagements = ad["engagements"]
                link_clicks = ad["link_clicks"]
                spend = ad["spend"]

                frequency = (
                    impressions / reach
                    if reach
                    else 0
                )

                ctr = calculate_percentage(
                    link_clicks,
                    impressions
                )

                engagement_rate = calculate_percentage(
                    engagements,
                    impressions
                )

                cost_per_reach = (
                    spend / reach
                    if reach
                    else 0
                )

                ads.append({
                    "ad_name": ad["ad_name"],
                    "reach": int(reach),
                    "impressions": int(impressions),
                    "engagements": int(engagements),
                    "link_clicks": int(link_clicks),
                    "frequency": round(frequency, 2),
                    "ctr": round(ctr, 2),
                    "engagement_rate": round(
                        engagement_rate,
                        2
                    ),
                    "cost_per_reach": round(
                        cost_per_reach,
                        2
                    ),
                    "amount_spent": round(
                        spend,
                        2
                    ),
                })

            # ==========================================================
            # 4. Calculate TOTAL
            # ==========================================================

            total_reach = sum(
                ad["reach"] for ad in ads
            )

            total_impressions = sum(
                ad["impressions"] for ad in ads
            )

            total_engagements = sum(
                ad["engagements"] for ad in ads
            )

            total_link_clicks = sum(
                ad["link_clicks"] for ad in ads
            )

            total_spend = sum(
                ad["amount_spent"] for ad in ads
            )

            total_frequency = (
                total_impressions / total_reach
                if total_reach
                else 0
            )

            total_ctr = calculate_percentage(
                total_link_clicks,
                total_impressions
            )

            total_engagement_rate = calculate_percentage(
                total_engagements,
                total_impressions
            )

            total_cost_per_reach = (
                total_spend / total_reach
                if total_reach
                else 0
            )

            total = {
                "reach": int(total_reach),
                "impressions": int(total_impressions),
                "engagements": int(total_engagements),
                "link_clicks": int(total_link_clicks),
                "frequency": round(
                    total_frequency,
                    2
                ),
                "ctr": round(
                    total_ctr,
                    2
                ),
                "engagement_rate": round(
                    total_engagement_rate,
                    2
                ),
                "cost_per_reach": round(
                    total_cost_per_reach,
                    2
                ),
                "amount_spent": round(
                    total_spend,
                    2
                ),
            }

            # ==========================================================
            # 5. Final result
            # ==========================================================

            result = {
                "success": True,
                "overview": {
                    "client_id": str(client_id),
                    "period_id": period_id,
                    "objective": objective,
                    "ads": ads,
                    "total": total,
                }
            }

            print("\n[DEBUG] NUMBER OF ADS:", len(ads))

            print("\n[DEBUG] ADS:")
            for ad in ads:
                print(ad)

            print("\n[DEBUG] TOTAL:")
            print(total)

            return result

    except Exception as e:

        print(
            f"[ERROR] {type(e).__name__}: {e}"
        )

        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()

@tool
def content_analysis(
    client_code: str,
    period_id: str,
    objective: str,
    top_n: int = 5
) -> dict:
    """
    Retrieve top-performing ad creatives for content analysis
    based on client, reporting period, objective, and ranking.
    """

    conn = get_connection()

    try:
        objective = objective.lower().strip()

        objective_mapping = {
            "reach": "reach",
            "engagement": "post_engagement",
            "views": "video_view",
            "link clicks": "link_click",
            "leads": "lead",
        }

        result_type = objective_mapping.get(objective)

        if result_type is None:
            return {
                "success": False,
                "message": f"Objective '{objective}' is not available."
            }

        # Prevent unreasonable top_n
        top_n = max(1, min(top_n, 20))

        with conn.cursor() as cursor:

            # ==========================================================
            # 1. Retrieve ad performance
            # ==========================================================

            cursor.execute(
                """
                SELECT
                    ap.client_id,
                    ap.ad_external_id,
                    ap.ad_name,
                    ap.reach,
                    ap.impressions,
                    ap.post_engagements,
                    ap.link_clicks,
                    ap.spend
                FROM meta_ads_ad_performance ap

                INNER JOIN clients c
                    ON c.id = ap.client_id

                INNER JOIN meta_ads_report_periods rp
                    ON rp.id = ap.meta_ads_report_period_id

                WHERE
                    c.client_code = %s
                    AND rp.period_start = %s
                    AND LOWER(ap.result_type) = LOWER(%s)

                ORDER BY ap.reach DESC

                LIMIT %s;
                """,
                (
                    client_code,
                    period_id,
                    result_type,
                    top_n,
                ),
            )

            rows = cursor.fetchall()

            print("\n========================================")
            print("[DEBUG] CONTENT ANALYSIS")
            print("========================================")
            print(f"[DEBUG] client_code : {client_code}")
            print(f"[DEBUG] period_id   : {period_id}")
            print(f"[DEBUG] objective   : {objective}")
            print(f"[DEBUG] result_type : {result_type}")
            print(f"[DEBUG] rows        : {len(rows)}")

            if not rows:
                return {
                    "success": False,
                    "message": "Content analysis data not found."
                }

            # ==========================================================
            # 2. Build creative ranking
            # ==========================================================

            creatives = []

            for index, row in enumerate(rows, start=1):

                client_id = row[0]
                ad_external_id = row[1]
                ad_name = row[2]

                reach = to_number(row[3]) or 0
                impressions = to_number(row[4]) or 0
                engagements = to_number(row[5]) or 0
                link_clicks = to_number(row[6]) or 0
                spend = to_number(row[7]) or 0

                engagement_rate = calculate_percentage(
                    engagements,
                    impressions
                )

                ctr = calculate_percentage(
                    link_clicks,
                    impressions
                )

                cost_per_reach = (
                    spend / reach
                    if reach
                    else 0
                )

                creative = {
                    "rank": index,
                    "ad_external_id": ad_external_id,
                    "ad_name": ad_name,

                    "performance": {
                        "reach": int(reach),
                        "impressions": int(impressions),
                        "engagements": int(engagements),
                        "link_clicks": int(link_clicks),
                        "engagement_rate": engagement_rate,
                        "ctr": ctr,
                        "cost_per_reach": round(
                            cost_per_reach,
                            2
                        ),
                        "amount_spent": round(
                            spend,
                            2
                        ),
                    }
                }

                creatives.append(creative)

            # ==========================================================
            # 3. Best Creative
            # ==========================================================

            best_creative = creatives[0]

            # ==========================================================
            # 4. Final result
            # ==========================================================

            result = {
                "success": True,

                "content_analysis": {
                    "client_id": str(client_id),
                    "period_id": period_id,
                    "objective": objective,

                    "best_creative": best_creative,

                    "creatives": creatives
                }
            }

            print("\n[DEBUG] BEST CREATIVE:")
            print(best_creative)

            print("\n[DEBUG] CREATIVE RANKING:")

            for creative in creatives:
                print(
                    f"{creative['rank']}. "
                    f"{creative['ad_name']} | "
                    f"Reach: {creative['performance']['reach']} | "
                    f"ER: {creative['performance']['engagement_rate']}% | "
                    f"CPR: {creative['performance']['cost_per_reach']}"
                )

            return result

    except Exception as e:

        print(
            f"[ERROR] {type(e).__name__}: {e}"
        )

        return {
            "success": False,
            "error": str(e),
        }

    finally:
        conn.close()


# ==============================================================
# DEBUG
# ==============================================================

if __name__ == "__main__":

    result = content_analysis.invoke({
        "client_code": "bourbon",
        "period_id": "2026-07-01",
        "objective": "reach",
        "top_n": 5,
    })

    print("\n")
    print("========================================")
    print("FINAL CONTENT ANALYSIS")
    print("========================================")
    print(result)