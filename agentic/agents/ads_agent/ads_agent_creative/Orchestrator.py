from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, TaskDelegation
from agentic.utils.logger import node, console

PLATFORM_RUNNERS = {
    "meta": "MetaRunner",
    "instagram": "instagram_runner",
    "facebook": "facebook_runner",
    "youtube": "youtube_runner",
    "tiktok": "tiktok_runner",
}

def orchestrator_agent(state: State):

    with node("Selecting Platform Runner"):

        request = state.request
        metadata = state.Metadata

        task_delegation = []

        for platform in request.platform_scope:

            platform = platform.lower().strip()
            runner = PLATFORM_RUNNERS.get(platform)

            if not runner:
                console.print(
                    f"[red]Unsupported platform:[/red] {platform}"
                )
                continue

            task_delegation.append(
                TaskDelegation(
                    client_code=metadata.client_code,
                    runner=runner,
                )
            )

        console.print(
            "[cyan]Selected Platforms:[/cyan]"
        )

        for task in task_delegation:
            console.print(
                f"  [bold]→ {task.runner}[/bold]"
            )

        return {
            "Task_delegation": task_delegation,
        }