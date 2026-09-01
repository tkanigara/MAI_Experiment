from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, FacebookMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.fb_reach import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any

def fb_reach_agent(state: State) -> State:
    with node("Facebook Ads Reach Analysis running"):
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
            performance_overview_reach = result["performance_overview_reach"],
            content_analysis_reach = result["content_analysis_reach"],
            placement_analysis_reach= result["placement_analysis_reach"],
            audience_demographic_analysis_reach = result["audience_demographic_analysis_reach"],
            region_analysis_reach=result["region_analysis_reach"],
            optimisation_action_reach=result["optimisation_action_reach"]

        )

    return {
        "facebook_result":facebook_result
    }
