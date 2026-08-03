from langchain_core.tools import tool
from config.db import get_connection
from decimal import Decimal
import json

def convert_number(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    return value

@tool
def retrieve_kpi(client_code: str, report_date: str, platform: str) -> dict:
    """
    Retrieve KPI Target and KPI result based on client_code, report_date and platform"""
    pass

@tool
def  retrieve_socmed_overview(client_code: str, report_date: str):
    """
    Retrieve social media overview based on client_code and report_date
    """
    pass

@tool
def retrieve_followers_growth(client_code: str, report_date: str):
    """
    Retrieve followers growth data based on client_code and report_date
    """
    pass

@tool
def retrieve_followers_growth_history(client_code: str, current_report_period_id: str):
    """
    Retrieve followers growth history based on client_code and current_report_period_id
    """
    pass

@tool
def retrieve_engagement_performance(client_code: str, report_date: str):
    """
    Retrieve engagement performance data based on client_code and report_date
    """
    pass

@tool
def retrieve_engagement_performance_history(client_code: str, current_report_period_id: str):
    """
    Retrieve engagement performance history based on client_code and current_report_period_id
    """
    pass

@tool
def retrieve_content_by_bucket(client_code: str, report_date: str, platform: str, bucket: str):
    """
    Retrieve content data based on client_code, report_date, platform and bucket
    """
    pass

@tool
def retrieve_all_content(client_code: str, report_date: str, platform: str) -> dict:
    """
    Retrieve all content data based on client_code, report_date and platform
    """
    pass    

@tool
def retrieve_competitor_analysis(client_code: str, report_date: str, platform: str):
    """
    Retrieve competitor analysis data based on client_code, report_date and platform
    """
    pass

@tool
def retrieve_instagram_performance(client_code: str, report_date: str):
    """
    Retrieve Instagram performance data based on client_code and report_date
    """
    pass
