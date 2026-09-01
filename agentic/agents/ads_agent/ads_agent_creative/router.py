from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.utils.logger import node
from rich.console import Console

console = Console()


AGENT_NAME = {
    "meta_runner_node": "All Meta Selected",
    "ig_runner_node": "Instagram Selected",
    "fb_runner_node": "Facebook Selected",
    "tt_runner_node": "TikTok Selected",
    "yt_runner_node": "YouTube Selected",
    "linkedin_runner_node": "Linkedin Selected",
    "threads_runner_node": "Threads Selected"
}


RUNNER_TO_ROUTE = {
    "MetaRunner": "meta_runner_node",
    "InstagramRunner": "ig_runner_node",
    "FacebookRunner": "fb_runner_node",
    "TikTokRunner": "tt_runner_node",
    "YoutubeRunner": "yt_runner_node",
    "LinkedinRunner": "linkedin_runner_node",
    "ThreadsRunner": "threads_runner_node"
}


def router_node(state: State) -> State:
    with node("Runner Selections"):
        routes = []
        task_delegation = state.Task_delegation

        for task in task_delegation:
            route = RUNNER_TO_ROUTE.get(task.runner)
            if route:
                routes.append(route)

        state.routes = routes
        console.print("\n[bold cyan] Agent findings [/bold cyan]\n")

        for i, route in enumerate(routes, start=1):
            console.print(
                f"{i}. {AGENT_NAME[route]}"
            )

        console.print(
            f"\n[green]Total Agents: {len(routes)}[/green]"
        )

    return state
