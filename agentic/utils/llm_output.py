from langchain_core.messages import AIMessage

def get_llm_text(response: AIMessage) -> str:
    content = response.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []

        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))

        return "\n".join(texts)

    return str(content)