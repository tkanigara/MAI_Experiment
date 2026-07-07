from models.gemini import gemini
from CentralArch.state import State, MetaData
from langchain.agents import create_agent
from prompts.retrieval_prompts import SYSTEM_PROMPT
from tools.retrieval import TOOLS
import json
import re

def retrieval_agent(state: State) -> State:
    agent = create_agent(
        model=gemini,
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS
    )

    agent_input = f"""
Current Workflow:
{state.workflow.model_dump_json(indent=2)}

Request:
{state.request.model_dump_json(indent=2)}

Metadata:
{state.metadata.model_dump_json(indent=2)}

Decide which retrieval tools should be executed.
Use tools only.
Never fabricate data.
"""

    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": agent_input
            }
        ]
    })

    if "metadata" in result:
        state.metadata = MetaData(**result["metadata"])

    return state

