from tools.tools_list_ads_creative.retrieve_ig_data import performance_overview
result = performance_overview.invoke({
        "client_code": "bourbon",
        "report_period_id": "2026-07-01",
        "objective": "reach"
    })

print("\n=== PERFORMANCE OVERVIEW ===")
print(result)