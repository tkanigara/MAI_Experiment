from langchain_core.messages import HumanMessage, SystemMessage
from models.gemini import llm
from workflows.ads_workflow.adset_workflow.state import State, MetaAnalysis
from prompts.adset_prompts_list.meta_views_prompt import SYSTEM_PROMPT

def meta_reach_agent(state: State):
    #retrieve Data
    overall_views_data = """
    Data yang harus di retrive adalah nama client, periodnya dan data metric yang berisi gabungan dari semua adset objective views
    """
    campaign_views_data = """
    Data yang harus di retrieve adalah data campaign yang berisi masing masing adset dan metricnya ,dan jangan lupa data client dan periodnya 
    """

    data = {
        "overall_views_data":overall_views_data,
        "campaign_views_data":campaign_views_data
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=data)
    ]

    analysis = llm.invoke(messages)
    get_llm_analysis = analysis.content


    note = """
    node ini belum bisa di jalanin, SystemPrompt belum gw setting
    gw harus cek isi datanya dulu, dan format data yang di retrive kaya gimana
    """
    return state
