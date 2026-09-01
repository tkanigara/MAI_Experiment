from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, FacebookMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.fb_pagelike import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any

def fb_pagelike_agent(state: State) -> State:
    with node("Facebook Ads Engagement Analysis running"):
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

        facebook_result = FacebookMetricAnalysis(
            client_code=state.Metadata.client_code,
            performance_overview_pagelike = result["performance_overview_pagelike"],
            content_analysis_pagelike = result["content_analysis_pagelike"],
            placement_analysis_pagelike= result["placement_analysis_pagelike"],
            audience_demographic_analysis_pagelike= result["audience_demographic_analysis_pagelike"],
            region_analysis_pagelike=result["region_analysis_pagelike"],
            optimisation_action_pagelike=result["optimisation_action_pagelike"]

        )

    return {
        "facebook_result":facebook_result
    }
