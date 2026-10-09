from tools.tools_list_socmed.retrieva_ig_data import retrieve_instagram_performance

result = retrieve_instagram_performance.invoke({
    "client_code": "mai001",
    "report_date": "2026-09-30",
})

print(result)