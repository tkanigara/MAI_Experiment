from agentic.models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, SummaryAll
from agentic.prompts.ads_prompts_list.summary import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any

def summary_agent(state: State) -> State:
    with node("Summarizing ads analysis"):
        
        data = [state.instagram_result.model_dump(),
                state.facebook_result.model_dump(),
                state.youtube_result.model_dump(),
                state.tiktok_result.model_dump()
                ]
        messages =  [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=json.dump(data, indent=2, default=str))
        ]

        summary = llm.invoke(messages)
        content = summary.content

        if isinstance(content, list):
            text = "".join(
                part["text"]
                for part in content
                if part.get("type") == "text"
            )
        else:
            text = content
        text = text.strip()

        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = re.sub(r",(\s*[}\]])", r"\1", text)

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            print("JSON ERROR:", e)
            print(text)
            raise

        summary_result = SummaryAll(
            client_code=state.Metadata,
            summary_result=result["summary_result"]
        )
