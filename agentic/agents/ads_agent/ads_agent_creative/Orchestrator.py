from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, TaskDelegation


PLATFORM_RUNNERS = {
    "meta": "MetaRunner",
    "instagram": "InstagramRunner",
    "facebook": "FacebookRunner",
    "youtube": "YoutubeRunner",
    "tiktok": "TikTokRunner",
}


def _selected_platforms(scope: str) -> list[str]:
    scope = str(scope or "meta").strip().lower().replace("all_meta", "meta")
    if scope == "meta":
        return ["meta"]
    if scope in PLATFORM_RUNNERS:
        return [scope]
    return []


def orchestrator_agent(state: State):
    # Platform and objective are explicit in the request.  Letting an LLM
    # infer the platform from metadata made the old Ads graph fan out to every
    # objective and was especially error-prone for a single-platform run.
    task_delegation = [
        TaskDelegation(
            client_code=state.request.client_code,
            runner=PLATFORM_RUNNERS[platform],
        )
        for platform in _selected_platforms(state.request.platform_scope)
    ]
    return {"Task_delegation": task_delegation}
