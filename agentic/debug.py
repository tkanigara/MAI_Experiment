from pprint import pprint

from tools.retrieval_fb_data import (
    retrieve_engagement_performance,
    retrieve_engagement_performance_history,
    retrieve_followers_growth_history,
    retrieve_followers_growth
)

client_code = "mai001"
report_date = "2026-07-08"

# Current Period
current = retrieve_followers_growth.invoke(
    {
        "client_code": client_code,
        "report_date": report_date,
    }
)

print("===== CURRENT =====")
pprint(current)

if current["success"]:

    history = retrieve_followers_growth_history.invoke(
        {
            "client_code": client_code,
            "current_report_period_id": current["report_period_id"],
        }
    )

    print("\n===== HISTORY =====")
    pprint(history)