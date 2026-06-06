from models.gemini import gemini
from ..prompts.tes_prompt import SYSTEM_PROMPT
from .state import ReportState
from models.parser import parse_reasoning

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
