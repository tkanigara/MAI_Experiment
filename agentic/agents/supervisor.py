from models.gemini import gemini
from CentralArch.state import State
from langchain.agents import create_agent
from prompts.supervisor_prompt import SUPERVISOR_PROMPT, SYSTEM_PROMPT
import json
import re

def supervisor_agent(state: State) -> State:
    agent = create_agent(
        model=gemini,
        system_prompt=SYSTEM_PROMPT
    )

    user_message = f"""
        {state.request.model_dump()}
        {state.metadata.model_dump()}
        {state.workflow.model_dump()}
        """

    result = agent.invoke({
        "messages": [{"role": "user", "content": user_message}]
    })

    last_content = result["messages"][-1].content.strip()
    last_content = re.sub(r"^```json|```$", "", last_content, flags=re.MULTILINE).strip()

    parsed = json.loads(last_content)

    state.workflow.current_process = parsed["current_process"]
    state.workflow.current_agent = parsed["current_agent"]
    state.workflow.next_process = parsed["next_process"]
    state.workflow.next_agent = parsed["next_agent"]
    state.workflow.status = parsed["status"]
    return state

def retrieval_metadata(state: State):
    print("Retrieving metadata...")
    return state


def retrieval_report(state: State):
    print("Retrieving report...")
    return state