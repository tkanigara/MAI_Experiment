from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, YoutubeMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.yt_impressions import SYSTEM_PROMPT
from agentic.utils.logger import node
import json
import re
from typing import Any


def yt_impressions_agent(state: State) -> State:
    with node("Youtube Ads Impressions Analysis running"):
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

        youtube_result = YoutubeMetricAnalysis(
            client_code=state.Metadata.client_code,
            performance_overview_impressions = result["performance_overview_impressions"],
            audience_demographic_impressions= result["audience_demographic_impressions"],
            region_breakdown_impressions=result["region_breakdown_impressions"],
            testing_optimization_impressions=result[" testing_optimization_impressions"],
            bidding_optimisation_impressions=result["bidding_optimisation_impressions"]

        )

    return {
        "youtube_result":youtube_result
    }
