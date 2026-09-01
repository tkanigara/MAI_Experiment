from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, FacebookMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.fb_engagement import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any

def fb_engagement_agent(state: State) -> State:
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
            performance_overview_engagement = result["performance_overview_engagement"],
            content_analysis_engagement = result["content_analysis_engagement"],
            placement_analysis_engagement= result["placement_analysis_engagement"],
            audience_demographic_analysis_engagement= result["audience_demographic_analysis_engagement"],
            region_analysis_engagement=result["region_analysis_engagement"],
            optimisation_action_engagement=result["optimisation_action_engagement"]

        )

    return {
        "facebook_result":facebook_result
    }
