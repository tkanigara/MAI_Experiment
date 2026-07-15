import json
import re


def parse_llm_json(content: object) -> dict:
    if isinstance(content, list):
        text = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict)
        )
    else:
        text = str(content)

    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("LLM response must be a JSON object.")
    return result
