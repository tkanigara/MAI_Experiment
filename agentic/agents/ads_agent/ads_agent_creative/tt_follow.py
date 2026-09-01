from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, TiktokMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.tt_follow import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any

def tt_follow_agent(state: State) -> State:
    with node("TIktok Ads Follow Analysis running"):
        #tools data declaration

        data = {}
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=json.dump(data, indent=2, default=str))
        ]
        analysis = llm.invoke(messages)
        content = analysis.content

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

        tiktok_result = TiktokMetricAnalysis(
            client_code=state.Metadata.client_code,
            performance_overview_follow = result["performance_overview_follow"],
            audience_demographic_follow = result["audience_demographic_follow"],
            region_breakdown_follow=result["region_breakdown_follow"],
            optimisation_follow=result["optimisation_follow"]

        )

    return {
        "tiktok_result": tiktok_result
    }
