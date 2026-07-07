from langchain_core.tools import tool
from config.db import get_connection

@tool
def retrieval_metadata(client_code: str, report_date: str):
    """
    Retrieve client metadata for the specified report date.
    This includes information such as client profile, industry,
    reporting period, and other metadata required for report generation.
    """
    pass


@tool
def retrieval_kpi(client_code: str, report_date: str):
    """
    Retrieve key performance indicators (KPIs) for the specified client
    and report date.
    """
    pass


@tool
def retrieval_sosmed_overview(client_code: str, report_date: str):
    """
    Retrieve an overview of the client's social media performance,
    including overall metrics and summary statistics for the specified
    report date.
    """
    pass


@tool
def retrieval_followers_growth(client_code: str, report_date: str):
    """
    Retrieve follower growth metrics for the specified client and
    report date.
    """
    pass


@tool
def retrieval_engagement_performance(client_code: str, report_date: str):
    """
    Retrieve engagement performance metrics such as likes, comments,
    shares, impressions, and engagement rate for the specified client
    and report date.
    """
    pass
TOOLS = [
    retrieval_metadata,
    retrieval_kpi,
    retrieval_sosmed_overview,
    retrieval_followers_growth,
    retrieval_engagement_performance
]