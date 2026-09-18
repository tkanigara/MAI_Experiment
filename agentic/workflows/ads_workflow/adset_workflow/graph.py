from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from agentic.workflows.ads_workflow.adset_workflow.state import State

from agentic.agents.ads_agent.ads_set_agent.orchestrator import (
    orchestrator_node,
)

from agentic.agents.ads_agent.ads_set_agent.meta_runner import (
    meta_runner,
)


# ============================================================
# ROUTER
# ============================================================

def router(state: State):

    """
    Menentukan runner berdasarkan hasil
    task delegation dari orchestrator.
    """

    if not state.task_delegation:
        return END

    task = state.task_delegation[0]

    return task.runner


# ============================================================
# BUILD GRAPH
# ============================================================

workflow = StateGraph(State)


# ============================================================
# NODES
# ============================================================

workflow.add_node(
    "orchestrator",
    orchestrator_node,
)

workflow.add_node(
    "meta_runner",
    meta_runner,
)


# ============================================================
# START → ORCHESTRATOR
# ============================================================

workflow.add_edge(
    START,
    "orchestrator",
)


# ============================================================
# ORCHESTRATOR → ROUTER → RUNNER
# ============================================================

workflow.add_conditional_edges(
    "orchestrator",
    router,
    {
        "meta_runner": "meta_runner",
        END: END,
    },
)


# ============================================================
# RUNNER → END
# ============================================================

workflow.add_edge(
    "meta_runner",
    END,
)


# ============================================================
# COMPILE
# ============================================================

graph = workflow.compile()
