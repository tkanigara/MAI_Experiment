from langgraph.types import Send
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.utils.logger import node, console

FACEBOOK_OBJECTIVE_ROUTES = {
    "engagement": "facebook_engagement_agent",
    "reach": "facebook_reach_agent",
    "profile_visit": "facebook_profilevisit_agent",
    "pagelike": "facebook_pagelike_agent",
}


def facebook_runner_node(state: State):

    with node("Facebook Runner"):

        objectives = [
            objective.lower().strip()
            for objective in state.request.objectives
        ]

        sends = []

        for objective in objectives:

            agent_node = FACEBOOK_OBJECTIVE_ROUTES.get(
                objective
            )

            if not agent_node:
                console.print(
                    f"[red]Unsupported Facebook objective:[/red] "
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