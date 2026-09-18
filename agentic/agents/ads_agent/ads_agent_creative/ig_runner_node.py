from langgraph.types import Send
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.utils.logger import node, console

INSTAGRAM_OBJECTIVE_ROUTES = {
    "engagement": "instagram_engagement_agent",
    "reach": "instagram_reach_agent",
    "profile_visit": "instagram_profilevisit_agent",
}

def instagram_runner_node(state: State):

    with node("Instagram Runner"):

        objectives = [
            objective.lower().strip()
            for objective in state.request.objectives
        ]

        sends = []

        for objective in objectives:

            agent_node = INSTAGRAM_OBJECTIVE_ROUTES.get(
                objective
            )

            if not agent_node:
                console.print(
                    f"[red]Unsupported Instagram objective:[/red] "
                    f"{objective}"
                )
                continue

            console.print(
                f"[cyan]Routing:[/cyan] "
                f"[bold]{objective}[/bold] "
                f"→ [bold]{agent_node}[/bold]"
            )

            sends.append(
                Send(
                    agent_node,
                    state
                )
            )

        return sends