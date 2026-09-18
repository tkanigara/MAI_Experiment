from agentic.workflows.ads_workflow.ads_creative_workflow.state import State
from agentic.tools.tools_list_ads_creative.retrieval_metadata import retrieve_creative_metadata
from agentic.utils.logger import node, console

def retrieval_agent(state: State):
    with node("Starting retrieval metadata"):
        request = state.request
        metadata = retrieve_creative_metadata.invoke({
            "client_code": request.client_code,
            "period_id": request.period_id,
        })

        console.print("[cyan] Metadata retrieved [/cyan]")
        console.print("Metadata details /n")
        console.print(f"[cyan]{metadata}")
        
        return {
            "Metadata": metadata,
        }

