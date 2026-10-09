from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.utils.logger import node
from rich.console import Console

console = Console()
AGENT_NAME = {
    "meta_runner": "All Meta Selected",
    "instagram_runner": "Instagram Selected",
    "facebook_runner": "Facebook Selected",
    "tiktok_runner": "TikTok Selected",
    "youtube_runner": "YouTube Selected",

}

RUNNER_TO_ROUTE = {
    "meta_runner": "meta_runner",
    "instagram_runner": "instagram_runner",
    "facebook_runner": "facebook_runner",
    "tiktok_runner": "tiktok_runner",
    "youtube_runner": "youtube_runner",

}

def router_node(state: State) -> State:
    routes = []
    for task in state.Task_delegation:
        route = RUNNER_TO_ROUTE.get(task.runner)
        if route:
            routes.append(route)
    state.routes = routes
    return state