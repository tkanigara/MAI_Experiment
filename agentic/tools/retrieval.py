from langchain_core.tools import tool
from config.db import get_connection
from datetime import datetime

@tool
def retrieval_metadata(client_code: str) -> dict:
    """
    Retrieve client metadata based on client_code and report date.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT
                    id,
                    client_code,
                    client_name,
                    has_instagram,
                    has_facebook,
                    has_tiktok,
                    has_youtube
                FROM clients
                WHERE client_code = %s
                LIMIT 1;
            """

            cursor.execute(sql, (client_code,))
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
                }

            return {
                "client_id": row[0],
                "client_code": row[1],
                "client_name": row[2],
                "instagram": bool(row[3]),
                "facebook": bool(row[4]),
                "tiktok": bool(row[5]),
                "youtube": bool(row[6]),
                "loaded": True,
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
