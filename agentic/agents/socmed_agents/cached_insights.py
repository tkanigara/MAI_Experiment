from workflows.socmed_workflow.state import (
    State,
    SummaryAllSocmed,
    SummaryFacebook,
    SummaryInstagram,
    SummaryTiktok,
    SummaryYoutube,
    facebook_result_analysis,
    instagram_result_analysis,
    tiktok_result_analysis,
    youtube_result_analysis,
)
from repositories.report_insights import load_cached_agent_results
from utils.logger import node


RESULT_MODELS = {
    "instagram": ("instagram_result", instagram_result_analysis),
    "facebook": ("facebook_result", facebook_result_analysis),
    "tiktok": ("tiktok_result", tiktok_result_analysis),
    "youtube": ("youtube_result", youtube_result_analysis),
}

SUMMARY_MODELS = {
    "instagram": ("summary_instagram", SummaryInstagram),
    "facebook": ("summary_facebook", SummaryFacebook),
    "tiktok": ("summary_tiktok", SummaryTiktok),
    "youtube": ("summary_youtube", SummaryYoutube),
}


def cached_insights_node(state: State) -> State:
    with node("Check analysis cache"):
        if not state.request.reuse_cached_insights:
            return state
        if not state.Metadata.client_id or not state.Metadata.report_period_id:
            return state

        connected = [
            platform
            for platform in RESULT_MODELS
            if getattr(state.Metadata, platform, False)
        ]
        cached = load_cached_agent_results(
            state.Metadata.client_id,
            state.Metadata.report_period_id,
            connected,
        )
        if not cached:
            return state

        for platform, values in cached["platforms"].items():
            state_field, result_model = RESULT_MODELS[platform]
            setattr(
                state,
                state_field,
                result_model(
                    client_code=state.Metadata.client_code,
                    client_name=state.Metadata.client_name,
                    **values,
                ),
            )
        for platform, values in cached["summaries"].items():
            state_field, summary_model = SUMMARY_MODELS[platform]
            setattr(
                state,
                state_field,
                summary_model(
                    client_code=state.Metadata.client_code,
                    **values,
                ),
            )
        state.summary_all_socmed = SummaryAllSocmed(
            client_code=state.Metadata.client_code,
            summary=cached["executive_summary"],
        )
        state.analysis_cache_hit = True
        state.analysis_data_version = cached["data_version"]
    return state
