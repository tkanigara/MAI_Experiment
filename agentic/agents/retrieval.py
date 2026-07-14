from CentralArch.state import State, MetaData
from tools.retrieval import retrieval_metadata
from utils.logger import node
import json
import re

def retrieval_agent(state: State) -> State:
    with node("Retrieve Metadata"):
        if not state.Metadata.loaded:
            Metadata = retrieval_metadata.invoke({
                "client_code": state.request.client_code,
                "report_date": state.request.report_date.isoformat()
            })

            state.Metadata = MetaData(**Metadata)
    return state