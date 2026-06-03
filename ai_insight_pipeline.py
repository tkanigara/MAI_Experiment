import json
import os
import re

from analytics_pipeline import number


REQUIRED_FIELDS = [
    "executive_summary",
    "ig_reach_insight_summary",
    "engagement_trend_text",
    "top_content_success_driver",
    "content_type_insight",
    "summary_point_1",
    "summary_point_2",
    "summary_point_3",
    "summary_point_4",
    "recommendation_1",
    "recommendation_2",
    "recommendation_3",
]


def fmt_number(value):
    return f"{int(round(number(value))):,}"


def fmt_percent(value):
    return f"{number(value):.2f}%"


def extract_json_object(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Gemini response does not contain a JSON object.")
    return json.loads(match.group(0))


def fallback_insights(kpi_summary, warning=""):
    best_type = kpi_summary.get("best_content_type") or "konten dengan interaksi tertinggi"
    total_reach = fmt_number(kpi_summary.get("total_reach", 0))
    total_views = fmt_number(kpi_summary.get("total_views", 0))
    total_interactions = fmt_number(kpi_summary.get("total_interactions", 0))
    avg_er = fmt_percent(kpi_summary.get("avg_engagement_rate", 0))
    total_posts = fmt_number(kpi_summary.get("total_posts", 0))

    top_content = kpi_summary.get("top_3_content") or kpi_summary.get("top_posts") or []
    top_caption = ""
    if top_content:
        top_caption = str(top_content[0].get("caption", "")).strip()[:140]

    result = {
        "executive_summary": (
            f"Instagram menghasilkan {total_reach} reach, {total_views} views, "
            f"dan {total_interactions} interactions dari {total_posts} post."
        ),
        "ig_reach_insight_summary": (
            f"Reach periode ini mencapai {total_reach}; kualitas distribusi perlu dibaca bersama ER {avg_er}."
        ),
        "engagement_trend_text": (
            f"Total interactions mencapai {total_interactions} dengan average engagement rate {avg_er}."
        ),
        "top_content_success_driver": (
            f"Top content terkuat berasal dari format {best_type}."
            + (f" Tema/caption yang menonjol: {top_caption}." if top_caption else "")
        ),
        "content_type_insight": (
            f"Format dengan kontribusi interaksi terbaik saat ini adalah {best_type}."
        ),
        "summary_point_1": f"Total post Instagram: {total_posts}.",
        "summary_point_2": f"Total reach Instagram: {total_reach}.",
        "summary_point_3": f"Total interactions Instagram: {total_interactions}.",
        "summary_point_4": f"Average engagement rate: {avg_er}.",
        "recommendation_1": f"Prioritaskan format {best_type} untuk konten berikutnya.",
        "recommendation_2": "Gunakan top content sebagai acuan visual, hook, dan struktur caption.",
        "recommendation_3": "Tambahkan target dan benchmark agar evaluasi performa lebih tajam.",
    }
    if warning:
        result["warning"] = warning
    return result


def generate_ai_insight(kpi_summary, client_id="", frequency=""):
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback_insights(kpi_summary, "Gemini API key not configured; using rule-based fallback.")

    try:
        import google.generativeai as genai

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        compact_payload = {
            "client_id": client_id,
            "frequency": frequency,
            "instagram": {
                "total_posts": kpi_summary.get("total_posts", 0),
                "total_reach": kpi_summary.get("total_reach", 0),
                "total_views": kpi_summary.get("total_views", 0),
                "total_likes": kpi_summary.get("total_likes", 0),
                "total_comments": kpi_summary.get("total_comments", 0),
                "total_shares": kpi_summary.get("total_shares", 0),
                "total_saved": kpi_summary.get("total_saved", 0),
                "total_interactions": kpi_summary.get("total_interactions", 0),
                "avg_engagement_rate": kpi_summary.get("avg_engagement_rate", 0),
                "best_content_type": kpi_summary.get("best_content_type", ""),
                "feed_stats": kpi_summary.get("feed_stats", {}),
                "reels_stats": kpi_summary.get("reels_stats", {}),
                "top_3_content": kpi_summary.get("top_3_content", []),
            },
        }

        prompt = f"""
You are a senior social media analyst. Create concise Indonesian insights for an
Instagram-only recurring report.

Return ONLY valid JSON with exactly these string fields:
{json.dumps(REQUIRED_FIELDS, ensure_ascii=False)}

Rules:
- Use only KPI_DATA. Do not invent benchmarks, paid ads, or competitor facts.
- Mention concrete numbers when useful.
- Keep every value short enough for Google Slides.
- No Markdown bullets.

KPI_DATA:
{json.dumps(compact_payload, ensure_ascii=False, indent=2)}
"""
        response = model.generate_content(prompt)
        parsed = extract_json_object(response.text or "")
        result = {field: str(parsed.get(field, "")).strip() for field in REQUIRED_FIELDS}
        missing = [field for field, value in result.items() if not value]
        if missing:
            fallback = fallback_insights(kpi_summary)
            for field in missing:
                result[field] = fallback[field]
            result["warning"] = f"Gemini response missed fields: {', '.join(missing)}."
        return result
    except Exception as exc:
        return fallback_insights(kpi_summary, f"Gemini failed; using rule-based fallback. Error: {exc}")
