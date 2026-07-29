from CentralArch.state import State
from utils.logger import node
from rich.console import Console

console = Console()

AGENT_NAME = {
    "ig_analysis_agent": "Instagram Analysis running",
    "fb_analysis_agent": "Facebook Analysis running",
    "tt_analysis_agent": "TikTok Analysis running",
    "yt_analysis_agent": "YouTube Analysis running",
}

def router_node(state: State) -> State:
    with node("Agents Selections"):
        routes = []
        metadata = state.Metadata

        if metadata.instagram:
            routes.append("ig_analysis_agent")

        if metadata.facebook:
            routes.append("fb_analysis_agent")

        if metadata.tiktok:
            routes.append("tt_analysis_agent")

        if metadata.youtube:
            routes.append("yt_analysis_agent")

        state.routes = routes

        console.print("\n[bold cyan] Agent findings [/bold cyan]\n")

        for i, route in enumerate(routes, start=1):
            console.print(f"{i}. {AGENT_NAME[route]}")

        console.print(f"\n[green]Total Agents: {len(routes)}[/green]")
    return state