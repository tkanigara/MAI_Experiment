import json
from langchain_core.messages import HumanMessage, SystemMessage
from agentic.models.gemini import llm
from agentic.workflows.ads_workflow.adset_workflow.state import State, MetaAnalysis
from agentic.prompts.adset_prompts_list.meta_views_prompt import SYSTEM_PROMPT
from agentic.tools.tools_adset.retrieve_meta import views_retrieval
from agentic.utils.logger import node, console
from agentic.agents.ads_agent.ads_set_agent.data_source import get_adset_evidence

def meta_views_agent(state: State):
    with node("Meta views Agent"):
        data = get_adset_evidence(state, "views", views_retrieval)

        data_for_llm = json.dumps(
            data,
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
            analysis_data = json.loads(result)

        except (json.JSONDecodeError, TypeError):
            return {
                "meta_analysis": state.meta_analysis
            }

        console.print("[cyan]Meta views Analysis result: [/cyan]")
        console.print(json.dumps(analysis_data, indent=2, ensure_ascii=False))
        updated_meta_analysis = state.meta_analysis.model_copy(
            update={
                "overall_views_analysis":
                    analysis_data.get(
                        "overall_views_analysis"
                    ),

                "views_adset_analysis":
                    analysis_data.get(
                        "views_adset_analysis"
                    ),
            }
        )

        return {
            "meta_analysis": updated_meta_analysis
        }

