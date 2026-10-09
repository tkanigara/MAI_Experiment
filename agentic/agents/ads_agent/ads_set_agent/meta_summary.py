import json
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.adset_workflow.state import State, MetaSummary
from agentic.prompts.adset_prompts_list.meta_summary_prompt import SYSTEM_PROMPT
from agentic.utils.logger import node, console
def meta_summary_agent(state: State):
    with node("Meta summary"):
        analysis_data = state.meta_analysis.model_dump()
        data_for_llm = json.dumps(
            analysis_data,
            indent=2,
            default=str,
        )

        messages = [
            SystemMessage(
                content=SYSTEM_PROMPT
            ),
            HumanMessage(
                content=data_for_llm
            ),
        ]

        response = llm.invoke(messages)
        result = response.content
        try:
            if isinstance(result, list):
                text_parts = []
                for part in result:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            text_parts.append(
                                part.get("text", "")
                            )

                result = "\n".join(text_parts)
            summary_data = json.loads(result)

        except (json.JSONDecodeError, TypeError):
            return {
                "meta_summary": MetaSummary(
                    summary_result=None
                )
            }

        console.print("[cyan] Meta summary result: [/cyan]")
        console.print(json.dumps(summary_data, indent=2, ensure_ascii= False))
        return {
            "meta_summary": MetaSummary(
                summary_result=summary_data.get(
                    "summary_result"
                )
            )
        }

