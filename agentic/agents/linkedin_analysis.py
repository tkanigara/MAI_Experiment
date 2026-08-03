from CentralArch.state import State, linkedin_result_analysis
from models.gemini import llm
from langchain_core.messages import HumanMessage, SystemMessage
from prompts.linkedin_analysis_prompt import SYSTEM_PROMPT
from tools.retrieve_ll_data import retrieve_kpi, retrieve_socmed_overview, retrieve_followers_growth, retrieve_engagement_performance, retrieve_content_by_bucket,retrieve_followers_growth_history, retrieve_engagement_performance_history, retrieve_competitor_analysis
import json
import re

def linkedin_analysis_agent(state: State) -> State:
    pass
