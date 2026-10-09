from workflows.socmed_workflow.state import State
from repositories.report_insights import persist_agent_results
from utils.logger import node


def persist_insights_node(state: State) -> State:
    with node("Persist report insights"):
        if not state.request.persist_insights:
            return state
        result = persist_agent_results(state)
        state.analysis_data_version = result["data_version"]
    return state
