from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, InstagramMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.ig_profile import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any

def ig_profilevisit_agent(state: State) -> State:
    with node("Instagram Ads Profile visit Analysis running"):
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

        instagram_result = InstagramMetricAnalysis(
            client_code=state.Metadata.client_code,
            performance_overview_profilevisit = result["performance_overview_profilevisit"],
            content_analysis_profilevisit = result["content_analysis_profilevisit"],
            placement_analysis_profilevisit= result["placement_analysis_profilevisit"],
            audience_demographic_analysis_profilevisit= result["audience_demographic_analysis_profilevisit"],
            region_analysis_profilevisit=result["region_analysis_profilevisit"],
            optimisation_action_profilevisit=result["optimisation_action_profilevisit"]

        )

    return {
        "instagram_result":instagram_result
    }
