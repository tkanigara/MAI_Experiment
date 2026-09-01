from langchain_core.tools import tool
from agentic.config.db import get_connection
from datetime import datetime


@tool
def retrieval_metadata(client_code: str, platform_scope: str, period_id: str) -> dict:
    """
    Retrieve client metadata based on client_code, platform_scope, and period_id.
    client_code:
        Client code stored in public.clients.client_code.

    platform_scope:
        Platform scope such as 'meta', 'tiktok', 'youtube', etc.

    period_id:
        Report period start date in YYYY-MM-DD format.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        parsed_date = datetime.strptime(
            period_id,
            "%Y-%m-%d"
        ).date()

        platform = platform_scope.lower().strip()
        if platform == "meta":
            meta_query = """
                SELECT
                    c.id::text AS client_id,
                    c.client_code,
                    c.client_name,

                    rp.id::text AS report_period_id,
                    rp.period_start,
                    rp.period_end,

                    EXISTS (
                        SELECT 1
                        FROM public.meta_ads_placement_breakdown pb
                        WHERE pb.client_id = c.id
                        AND pb.meta_ads_report_period_id = rp.id
                        AND LOWER(TRIM(pb.publisher_platform)) = 'instagram'
                    ) AS instagram,

                    EXISTS (
                        SELECT 1
                        FROM public.meta_ads_placement_breakdown pb
                        WHERE pb.client_id = c.id
                        AND pb.meta_ads_report_period_id = rp.id
                        AND LOWER(TRIM(pb.publisher_platform)) = 'facebook'
                    ) AS facebook,

                    FALSE AS tiktok,
                    FALSE AS youtube,
                    FALSE AS linkedin,
                    FALSE AS threads

                FROM public.clients c

                INNER JOIN public.client_meta_ad_accounts maa
                    ON maa.client_id = c.id
                AND maa.is_active = TRUE

                INNER JOIN public.meta_ads_report_periods rp
                    ON rp.client_id = c.id

                WHERE c.client_code = %s
                AND rp.period_start = %s

                ORDER BY rp.period_end DESC

                LIMIT 1;
            """
            cursor.execute(
                meta_query,
                (
                    client_code,
                    parsed_date
                )
            )

            row = cursor.fetchone()
            if row is None:
                return {
                    "client_id": None,
                    "client_code": client_code,
                    "client_name": None,

                    "report_period_id": None,
                    "period_start": None,
                    "period_end": None,

                    "instagram": False,
                    "facebook": False,
                    "tiktok": False,
                    "youtube": False,
                    "linkedin": False,
                    "threads": False,

                    "loaded": False,

                    "error": (
                        f"Metadata not found for "
                        f"client_code='{client_code}', "
                        f"period_id='{period_id}'"
                    )
                }

            (
                db_client_id,
                db_client_code,
                client_name,

                report_period_id,
                period_start,
                period_end,

                instagram,
                facebook,
                tiktok,
                youtube,
                linkedin,
                threads,
            ) = row

            return {
                "client_id": db_client_id,
                "client_code": db_client_code,
                "client_name": client_name,

                "report_period_id": report_period_id,
                "period_start": period_start,
                "period_end": period_end,

                "instagram": instagram,
                "facebook": facebook,
                "tiktok": tiktok,
                "youtube": youtube,
                "linkedin": linkedin,
                "threads": threads,

                "loaded": True,
                "error": None
            }

        return {
            "client_id": None,
            "client_code": client_code,
            "client_name": None,

            "report_period_id": None,
            "period_start": None,
            "period_end": None,

            "instagram": False,
            "facebook": False,
            "tiktok": False,
            "youtube": False,
            "linkedin": False,
            "threads": False,

            "loaded": False,

            "error": (
                f"Unsupported platform_scope='{platform_scope}'"
            )
        }

    except ValueError:
        return {
            "client_id": None,
            "client_code": client_code,
            "client_name": None,

            "report_period_id": None,
            "period_start": None,
            "period_end": None,

            "instagram": False,
            "facebook": False,
            "tiktok": False,
            "youtube": False,
            "linkedin": False,
            "threads": False,

            "loaded": False,

            "error": (
                f"Invalid period_id='{period_id}'. "
                f"Expected format YYYY-MM-DD."
            )
        }

    except Exception as e:
        return {
            "client_id": None,
            "client_code": client_code,
            "client_name": None,

            "report_period_id": None,
            "period_start": None,
            "period_end": None,

            "instagram": False,
            "facebook": False,
            "tiktok": False,
            "youtube": False,
            "linkedin": False,
            "threads": False,

            "loaded": False,

            "error": str(e)
        }

    finally:
        cursor.close()
        conn.close()