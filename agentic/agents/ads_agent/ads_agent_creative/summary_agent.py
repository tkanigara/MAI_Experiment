from agentic.models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.workflows.ads_workflow.ads_creative_workflow.state import State, SummaryAll
from agentic.prompts.ads_prompts_list.summary import SYSTEM_PROMPT
from agentic.utils.logger import node
from agentic.utils.llm_output import get_llm_text
from agentic.utils.llm_retry import (
    invoke_with_rate_limit_retry,
    transient_error_message,
)
import json
import re
from typing import Any

def summary_agent(state: State) -> State:
    with node("Summarizing ads analysis"):
        ads_data = state.ads_data.model_dump(mode="json")
        # Detailed rows were already analysed by the objective agents. Sending
        # them again in the final summary needlessly consumes the same quota.
        dashboard_context = {
            key: ads_data.get(key)
            for key in (
                "status",
                "success",
                "client",
                "period",
                "analysis_type",
                "platform_scope",
                "objectives",
                "source",
                "warnings",
                "unconfirmed_count",
            )
        }
        data = {
            "ads_data": dashboard_context,
            "analysis_results": [
                state.instagram_result.model_dump(mode="json"),
                state.facebook_result.model_dump(mode="json"),
                state.youtube_result.model_dump(mode="json"),
                state.tiktok_result.model_dump(mode="json"),
            ],
        }
        messages =  [
            SystemMessage(
                content=(SYSTEM_PROMPT or "").strip()
                or "Summarize the supplied Ads analysis without inventing facts. Return JSON with key summary_result."
            ),
            HumanMessage(content=json.dumps(data, indent=2, default=str))
        ]

        try:
            summary = invoke_with_rate_limit_retry(
                llm,
                messages,
                label="Ads summary",
            )
        except Exception as exc:
            safe_error = transient_error_message(exc)
            if safe_error is None:
                raise
            return {
                "summary_result": SummaryAll(
                    client_code=state.Metadata.client_code or state.request.client_code,
                    summary_result=(
                        "Summary could not be generated because the "
                        f"{safe_error.lower()} Completed objective analyses "
                        "remain available in the platform results."
                    ),
                )
            }
        text = get_llm_text(summary).strip()

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
            client_code=state.Metadata.client_code or state.request.client_code,
            summary_result=result.get("summary_result")
        )
        return {"summary_result": summary_result}
