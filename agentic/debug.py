from pprint import pprint

from tools.retrieval_fb_data import retrieve_competitor_analysis

client_code = "mai001"
platform = "facebook"
report_date = "2026-07-08"

result = retrieve_competitor_analysis.invoke(
    {
        "client_code": client_code,
        "platform": platform,
        "report_date": report_date,
    }
)

print("===== COMPETITOR ANALYSIS =====")

if result["success"]:

    print("\n----- CLIENT -----")
    pprint(result["Client"])

    print("\n----- COMPETITORS -----")
    pprint(result["Competitors"])

    print(f"\nTotal Competitors: {len(result['Competitors'])}")

else:
    pprint(result)