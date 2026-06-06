import re

def parse_reasoning(text):

    action_match = re.search(
        r"Action:\s*(.*)",
        text
    )

    action_input_match = re.search(
        r"Action Input:\s*(.*)",
        text
    )

    final_match = re.search(
        r"Final Answer:\s*(.*)",
        text
    )

    return {

        "action":
            action_match.group(1).strip()
            if action_match else None,

        "action_input":
            action_input_match.group(1).strip()
            if action_input_match else None,

        "final_answer":
            final_match.group(1).strip()
            if final_match else None
    }