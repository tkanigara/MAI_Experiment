from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, MetaData
from agentic.tools.tools_list_ads_creative.retrieval_metadata import retrieval_metadata
from agentic.utils.logger import node
import json
import re
def retrieval_agent(state):

    print("Starting Retrieve Metadata")

    try:
        Metadata = retrieval_metadata.invoke({
            "client_code": state.request.client_code,
            "platform_scope": state.request.platform_scope,
            "period_id": state.request.period_id,
        })

        print("Finished Retrieve Metadata")

        print("\n" + "=" * 60)
        print("[DEBUG] RETRIEVED METADATA")
        print("=" * 60)
        print(Metadata)

        print("\n" + "=" * 60)
        print("[DEBUG] CURRENT STATE")
        print("=" * 60)
        print(state.model_dump())

        return {
            "Metadata": Metadata
        }

    except Exception as e:
        print("Failed Retrieve Metadata")
        print(e)
        raise