from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, TaskDelegation
from agentic.models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.orchestrator import SYSTEM_PROMPT
from agentic.utils.llm_output import get_llm_text
import json


def orchestrator_agent(state: State):

    metadata = state.Metadata
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=metadata.model_dump_json()
        )
    ]

    response = llm.invoke(messages)
    text = get_llm_text(response)

    print("\n" + "=" * 60)
    print("[DEBUG] ORCHESTRATOR RAW OUTPUT")
    print("=" * 60)
    print(repr(text))
    print("=" * 60)

    result = json.loads(text)

    task_delegation = [
        TaskDelegation(**task)
        for task in result["task_delegation"]
    ]

    print("\n[DEBUG] TASK DELEGATION")
    print(
        [task.model_dump() for task in task_delegation]
    )

    return {
        "Task_delegation": task_delegation
    }