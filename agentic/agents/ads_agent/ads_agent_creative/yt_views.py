from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, YoutubeMetricAnalysis
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.prompts.ads_prompts_list.yt_views import SYSTEM_PROMPTS
from agentic.utils.logger import node
import json
import re
from typing import Any


def yt_views_agent(state: State) -> State:
    with node("Youtube Ads Views Analysis running"):
        #tools data declaration

        data = {}
        messages = [
            SystemMessage(content=SYSTEM_PROMPTS),
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
            performance_overview_views = result["performance_overview_views"],
            audience_demographic_views= result["audience_demographic_views"],
            region_breakdown_views=result["region_breakdown_views"],
            testing_optimization_views=result[" testing_optimization_views"],
            bidding_optimisation_views=result["bidding_optimisation_views"]

        )

    return {
        "youtube_result":youtube_result
    }
