from CentralArch.state import ReportGenerationResult, State
from tools.slides_report import generate_slides_report
from utils.logger import node


def state_insight_overrides(state: State) -> list[dict]:
    rows = []
    platform_results = {
        "instagram": state.instagram_result,
        "facebook": state.facebook_result,
        "tiktok": state.tiktok_result,
        "youtube": state.youtube_result,
    }
    insight_keys = (
        "kpi_analysis",
        "socmed_overview_analysis",
        "followers_growth_analysis",
        "growth_performance_analysis",
        "top_content_performance",
    )
    for platform, result in platform_results.items():
        if not getattr(state.Metadata, platform, False):
            continue
        for insight_key in insight_keys:
            insight_text = getattr(result, insight_key, None)
            if insight_text:
                rows.append(
                    {
                        "platform": platform,
                        "insight_key": insight_key,
                        "insight_text": insight_text,
                    }
                )
    platform_summaries = {
        "instagram": state.summary_instagram,
        "facebook": state.summary_facebook,
        "tiktok": state.summary_tiktok,
        "youtube": state.summary_youtube,
    }
    for platform, summary in platform_summaries.items():
        if not getattr(state.Metadata, platform, False):
            continue
        for insight_key in ("key_summary", "action_plan"):
            insight_text = getattr(summary, insight_key, None)
            if insight_text:
                rows.append(
                    {
                        "platform": platform,
                        "insight_key": insight_key,
                        "insight_text": insight_text,
                    }
                )
    return rows


def slides_generation_node(state: State) -> dict:
    with node("Generate Google Slides report"):
        if not state.Metadata.client_id or not state.Metadata.report_period_id:
            return {
                "report_generation": ReportGenerationResult(
                    status="failed",
                    error="Client or report period metadata is incomplete.",
                )
            }

        result = generate_slides_report.invoke(
            {
                "client_id": state.Metadata.client_id,
                "report_period_id": state.Metadata.report_period_id,
                "dry_run": state.request.slides_dry_run,
                "insight_overrides": state_insight_overrides(state),
            }
        )
        return {
            "report_generation": ReportGenerationResult(
                status=result.get("status", "failed"),
                presentation_id=result.get("presentation_id"),
                presentation_url=result.get("presentation_url"),
                report_name=result.get("report_name"),
                error=result.get("error"),
            )
        }
