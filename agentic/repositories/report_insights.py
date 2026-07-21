from __future__ import annotations

import json

from config.db import get_connection


ANALYSIS_SECTIONS = {
    "kpi_analysis": "kpi",
    "socmed_overview_analysis": "overview",
    "followers_growth_analysis": "audience_growth",
    "growth_performance_analysis": "engagement",
    "top_content_performance": "content",
    "low_content_performance": "content",
    "competitor_analysis": "competitor",
}

SUMMARY_KEYS = ("key_summary", "action_plan")


def _data_version(cursor, client_id: str, report_period_id: str) -> str:
    cursor.execute(
        """
        SELECT COUNT(*) AS row_count, MAX(updated_at) AS latest_update
        FROM (
            SELECT updated_at FROM instagram_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM facebook_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM tiktok_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM youtube_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM kpi_results
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM social_content_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM competitor_profile_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
            UNION ALL
            SELECT updated_at FROM competitor_content_reports
            WHERE client_id = %(client_id)s AND report_period_id = %(period_id)s
        ) source_rows
        """,
        {"client_id": client_id, "period_id": report_period_id},
    )
    row_count, latest_update = cursor.fetchone()
    timestamp = latest_update.isoformat() if latest_update else "empty"
    return f"{row_count}:{timestamp}"


def current_data_version(client_id: str, report_period_id: str) -> str:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            return _data_version(cursor, client_id, report_period_id)
    finally:
        conn.close()


def _upsert_insight(
    cursor,
    client_id: str,
    report_period_id: str,
    platform: str | None,
    section_key: str,
    insight_key: str,
    insight_text: str,
    display_order: int,
    data_version: str,
) -> None:
    if platform is None:
        cursor.execute(
            """
            DELETE FROM report_insights
            WHERE client_id = %s
              AND report_period_id = %s
              AND platform IS NULL
              AND section_key = %s
              AND insight_key = %s
            """,
            (client_id, report_period_id, section_key, insight_key),
        )

    cursor.execute(
        """
        INSERT INTO report_insights (
            client_id, report_period_id, platform, section_key,
            insight_key, insight_text, display_order, source, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'agentic_ai', %s::jsonb)
        ON CONFLICT (
            client_id, report_period_id, platform, section_key, insight_key
        ) DO UPDATE SET
            insight_text = EXCLUDED.insight_text,
            display_order = EXCLUDED.display_order,
            source = EXCLUDED.source,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        (
            client_id,
            report_period_id,
            platform,
            section_key,
            insight_key,
            insight_text,
            display_order,
            json.dumps(
                {
                    "generated_by": "central_agent_graph",
                    "data_version": data_version,
                }
            ),
        ),
    )


def persist_agent_results(state) -> dict:
    client_id = state.Metadata.client_id
    report_period_id = state.Metadata.report_period_id
    if not client_id or not report_period_id:
        raise ValueError("client_id and report_period_id are required to persist insights.")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            data_version = _data_version(cursor, client_id, report_period_id)
            written = 0
            cursor.execute(
                """
                DELETE FROM report_insights
                WHERE client_id = %s
                  AND report_period_id = %s
                  AND platform IS NULL
                  AND insight_key = 'summary_result'
                  AND source = 'agentic_ai'
                """,
                (client_id, report_period_id),
            )
            platform_results = {
                "instagram": state.instagram_result,
                "facebook": state.facebook_result,
                "tiktok": state.tiktok_result,
                "youtube": state.youtube_result,
            }
            for platform, result in platform_results.items():
                if not getattr(state.Metadata, platform, False):
                    continue
                for order, (insight_key, section_key) in enumerate(
                    ANALYSIS_SECTIONS.items(), start=1
                ):
                    insight_text = getattr(result, insight_key, None)
                    if not insight_text:
                        continue
                    _upsert_insight(
                        cursor,
                        client_id,
                        report_period_id,
                        platform,
                        section_key,
                        insight_key,
                        insight_text,
                        order,
                        data_version,
                    )
                    written += 1

            platform_summaries = {
                "instagram": state.summary_instagram,
                "facebook": state.summary_facebook,
                "tiktok": state.summary_tiktok,
                "youtube": state.summary_youtube,
            }
            for platform, summary in platform_summaries.items():
                if not getattr(state.Metadata, platform, False):
                    continue
                for order, insight_key in enumerate(SUMMARY_KEYS, start=1):
                    insight_text = getattr(summary, insight_key, None)
                    if not insight_text:
                        continue
                    _upsert_insight(
                        cursor,
                        client_id,
                        report_period_id,
                        platform,
                        "platform_summary",
                        insight_key,
                        insight_text,
                        order,
                        data_version,
                    )
                    written += 1
        conn.commit()
        return {"written": written, "data_version": data_version}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_cached_agent_results(
    client_id: str,
    report_period_id: str,
    connected_platforms: list[str],
) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            data_version = _data_version(cursor, client_id, report_period_id)
            cursor.execute(
                """
                SELECT platform, insight_key, insight_text
                FROM report_insights
                WHERE client_id = %s
                  AND report_period_id = %s
                  AND source = 'agentic_ai'
                  AND metadata->>'data_version' = %s
                ORDER BY updated_at
                """,
                (client_id, report_period_id, data_version),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    cached = {platform: {} for platform in connected_platforms}
    summaries = {platform: {} for platform in connected_platforms}
    for platform, insight_key, insight_text in rows:
        if platform in summaries and insight_key in SUMMARY_KEYS:
            summaries[platform][insight_key] = insight_text
        elif platform in cached:
            cached[platform][insight_key] = insight_text

    required_keys = set(ANALYSIS_SECTIONS)
    if any(
        not required_keys.issubset(cached[platform])
        for platform in connected_platforms
    ):
        return None
    if any(
        not set(SUMMARY_KEYS).issubset(summaries[platform])
        for platform in connected_platforms
    ):
        return None
    return {
        "data_version": data_version,
        "platforms": cached,
        "summaries": summaries,
    }
