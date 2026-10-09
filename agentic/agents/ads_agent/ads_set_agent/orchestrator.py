from agentic.workflows.ads_workflow.adset_workflow.state import State, TaskDelegation
from agentic.utils.logger import node, console

RUNNER_BY_PLATFORM = {
    "meta": "meta_runner",
    "tiktok": "tiktok_runner",
    "youtube": "youtube_runner",
}


def orchestrator_node(state: State):
    with node("Selecting Platform"):
        request = state.request
        platforms = [
            platform.lower().strip()
            for platform in request.platform_scope
        ]
        objectives = [
            objective.lower().strip()
            for objective in request.objectives
        ]
        task_delegation: list[TaskDelegation] = []

        for platform in platforms:
            runner = RUNNER_BY_PLATFORM.get(platform)
            if not runner:
                continue
            task_delegation.append(
                TaskDelegation(
                    runner=runner,
                    platform=platform,
                    objectives=objectives,
                )
            )

        console.print(f"[yellow]Platforms:[/yellow]"
                      f"[bold]{', '.join(platforms)}[/bold]")

        console.print(
            f"[yellow]Runner:[/yellow]"
            f"[bold]{', '.join(task.runner for task in task_delegation)}[/bold]"
        )
        return {
            "task_delegation": task_delegation
        }