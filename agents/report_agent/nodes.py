import json

from models.gemini import gemini
from ..prompts.tes_prompt import SYSTEM_PROMPT
from .state import ReportState
from models.parser import parse_reasoning
from tools.registry import TOOLS_BY_NAME

def user_query(state: ReportState) -> ReportState:
    state["messages"].append({
        "role":"user",
        "content": state["user_query"]
    })

    return state

def reasoning(state: ReportState) -> ReportState:
    messages = [{
        "role": "system",
        "content": SYSTEM_PROMPT
    }] + state["messages"]

    response_model = gemini.invoke(messages)
    content = response_model.content

    if isinstance(content, list):

        first_item = content[0]

        # kalau item dictionary
        if isinstance(first_item, dict):

            reasoning_output = first_item.get(
                "text",
                ""
            ).strip()

        # kalau item string
        elif isinstance(first_item, str):

            reasoning_output = first_item.strip()

        else:
            reasoning_output = str(first_item).strip()

    else:
        reasoning_output = str(content).strip()

    parsed_output = parse_reasoning(reasoning_output)

    return {
        "messages":state["messages"] + [{
            "role":"assistant",
            "content": reasoning_output
        }],

        "action": parsed_output.get("action"),

        "action_input": parsed_output.get("action_input"),

        "final_answer": parsed_output.get("final_answer"),

        "observation": state.get("observation")
    }


def routing(state: ReportState) ->ReportState:
    if state["final_answer"]:
        return "final"
    if state["action"]:
        return "action"
    return "final"


def action(state: ReportState) -> ReportState:
    tool_name = state.get("action")
    tool = TOOLS_BY_NAME.get(tool_name)

    if not tool:
        observation = f"Tool not found: {tool_name}"
    else:
        action_input = state.get("action_input") or {}
        if isinstance(action_input, str):
            try:
                action_input = json.loads(action_input)
            except json.JSONDecodeError:
                action_input = {}
        try:
            observation = tool.invoke(action_input)
        except TypeError:
            observation = tool.invoke({})
        except Exception as exc:
            observation = f"Tool failed: {exc}"

    return {
        "messages": state["messages"] + [{
            "role": "tool",
            "content": str(observation),
        }],
        "user_query": state.get("user_query", ""),
        "thought": state.get("thought"),
        "action": None,
        "action_input": None,
        "observation": str(observation),
        "final_answer": None,
    }
