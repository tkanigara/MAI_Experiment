from CentralArch.state import State, MetaData
from tools.retrieval import retrieval_metadata
from utils.logger import node
import json
import re

def retrieval_agent(state: State) -> State:
    with node("Retrieve Metadata"):
        if not state.Metadata.loaded:
            if not state.request.client_code or not state.request.report_date:
                state.Metadata = MetaData(
                    error="client_code and report_date are required."
                )
                return state
            Metadata = retrieval_metadata.invoke({
                "client_code": state.request.client_code,
                "report_date": state.request.report_date.isoformat()
            })

            state.Metadata = MetaData(**Metadata)
    return state
