from agentic.workflows.ads_workflow.adset_workflow.state import State
from agentic.agents.ads_agent.ads_set_agent.meta_engagement_agent import meta_engagement_agent
from agentic.agents.ads_agent.ads_set_agent.meta_leads_agent import meta_leads_agent
from agentic.agents.ads_agent.ads_set_agent.meta_linkclicks_agent import meta_linkclicks_agent
from agentic.agents.ads_agent.ads_set_agent.meta_reach_agent import meta_reach_agent
from agentic.agents.ads_agent.ads_set_agent.meta_views_agent import meta_views_agent
from agentic.agents.ads_agent.ads_set_agent.meta_summary import meta_summary_agent
from agentic.utils.logger import node, console

META_OBJECTIVE_AGENTS = {
    "reach": meta_reach_agent,
    "engagement": meta_engagement_agent,
    "leads": meta_leads_agent,
    "linkclicks": meta_linkclicks_agent,
    "link_clicks": meta_linkclicks_agent,
    "views": meta_views_agent,
}
def meta_runner(state: State):

    with node("Meta Runner"):
        meta_task = None
        for task in state.task_delegation:
            if task.runner == "meta_runner":
                meta_task = task
                break

        if meta_task is None:
            console.print(
                "[yellow]No Meta task found[/yellow]"
            )

            return {
                "meta_analysis": state.meta_analysis,
                "meta_summary": state.meta_summary,
            }

        objectives = [
            objective.lower().strip()
            for objective in meta_task.objectives
        ]

        console.print(
            f"[cyan]Objectives:[/cyan] "
            f"[bold]{', '.join(objectives)}[/bold]"
        )

        current_state = state

        for objective in objectives:

            agent = META_OBJECTIVE_AGENTS.get(objective)
            if agent is None:
                console.print(
                    f"[red]Unsupported objective:[/red] "
                    f"{objective}"
                )
                continue

            console.print(
                f"[cyan]Running Agent:[/cyan] "
                f"[bold]{agent.__name__}[/bold]"
            )

            result = agent(current_state)

            if result:
                current_state = current_state.model_copy(
                    update=result
                )

        console.print(
            "[cyan]Running Agent:[/cyan] "
            "[bold]meta_summary_agent[/bold]"
        )

        summary_result = meta_summary_agent(
            current_state
        )

        if summary_result:
            current_state = current_state.model_copy(
                update=summary_result
            )

        return {
            "meta_analysis": current_state.meta_analysis,
            "meta_summary": current_state.meta_summary,
        }
