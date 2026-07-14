from tools.retrieva_ig_data import retrieve_all_content, retrieve_top_performing_content

result = retrieve_all_content.invoke({
    "client_code": "mai001",
    "report_date": "2026-06-08",
    "platform": "instagram"
})

print(f"retrieval All content{result}\n")

result_top_performance = retrieve_top_performing_content.invoke({
    "client_code": "mai001",
    "report_date": "2026-06-08",
    "platform": "instagram"
})

print(f"retrieval top performing content{result_top_performance}\n")