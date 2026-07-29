from langchain_core.tools import tool
from config.db import get_connection
from datetime import datetime

@tool
def retrieval_metadata(client_code: str, report_date: str) -> dict:
    """
    Retrieve client metadata based on client_code and report date.
    """
    conn = get_connection()
    try:
        parsed_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        with conn.cursor() as cursor:
            sql = """
                SELECT
                    c.id,
                    c.client_code,
                    c.client_name,
                    c.has_instagram,
                    c.has_facebook,
                    c.has_tiktok,
                    c.has_youtube,
                    rp.id,
                    rp.period_start,
                    rp.period_end
                FROM clients c
                LEFT JOIN LATERAL (
                    SELECT id, period_start, period_end
                    FROM report_periods
                    WHERE client_id = c.id
                      AND period_start <= %s
                      AND period_end >= %s
                    ORDER BY period_start DESC
                    LIMIT 1
                ) rp ON TRUE
                WHERE c.client_code = %s
                LIMIT 1;
            """

            cursor.execute(sql, (parsed_date, parsed_date, client_code))
            row = cursor.fetchone()

            if row is None:
                return {
                    "client_id": None,
                    "client_code": None,
                    "client_name": None,
                    "instagram": False,
                    "facebook": False,
                    "tiktok": False,
                    "youtube": False,
                    "loaded": False,
                    "error": "Client not found.",
                }

            return {
                "client_id": str(row[0]),
                "client_code": row[1],
                "client_name": row[2],
                "instagram": bool(row[3]),
                "facebook": bool(row[4]),
                "tiktok": bool(row[5]),
                "youtube": bool(row[6]),
                "report_period_id": str(row[7]) if row[7] else None,
                "period_start": row[8],
                "period_end": row[9],
                "loaded": True,
                "error": None if row[7] else "Report period not found for the requested date.",
            }

    except ValueError:
        return {
            "client_id": None,
            "client_code": None,
            "client_name": None,
            "instagram": False,
            "facebook": False,
            "tiktok": False,
            "youtube": False,
            "loaded": False,
            "error": "Invalid report_date format. Expected YYYY-MM-DD."
        }
    finally:
        conn.close()