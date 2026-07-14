from CentralArch.graph import app
from CentralArch.state import (
    State,
    Request, 
    instagram_result_analysis, facebook_result_analysis, tiktok_result_analysis, youtube_result_analysis
)
from datetime import date

initial_state = State(
    request=Request(
        user_intent="Generate Marketing Report",
        client_code="mai001",
        report_date=date(2026, 6, 8)
    ),
)

result = app.invoke(initial_state)

instagram = result["instagram_result"]

print("===============INSTAGRAM ANALYSIS RESULT ==========")
print("===========================================")
print("=== KPI Analysis ===")
print(instagram.kpi_analysis)

print("\n=== Social Media Overview ===")
print(instagram.socmed_overview_analysis)

print("\n=== Followers Growth ===")
print(instagram.followers_growth_analysis)

print("\n=== Engagement Performance ===")
print(instagram.growth_performance_analysis)


facebook = result["facebook_result"]
print("===============FACEBOOK ANALYSIS RESULT ==========")
print("===========================================")
print("=== KPI Analysis ===")
print(facebook.kpi_analysis)

print("\n=== Social Media Overview ===")
print(facebook.socmed_overview_analysis)

print("\n=== Followers Growth ===")
print(facebook.followers_growth_analysis)

print("\n=== Engagement Performance ===")
print(facebook.growth_performance_analysis)

tiktok = result["tiktok_result"]
print("===============TIKTOK ANALYSIS RESULT ==========")
print("===========================================")
print("=== KPI Analysis ===")
print(tiktok.kpi_analysis)

print("\n=== Social Media Overview ===")
print(tiktok.socmed_overview_analysis)

print("\n=== Followers Growth ===")
print(tiktok.followers_growth_analysis)

print("\n=== Engagement Performance ===")
print(tiktok.growth_performance_analysis)

youtube = result["youtube_result"]
print("===============YOUTUBE ANALYSIS RESULT ==========")
print("===========================================")
print("=== KPI Analysis ===")
print(youtube.kpi_analysis)

print("\n=== Social Media Overview ===")
print(youtube.socmed_overview_analysis)

print("\n=== Followers Growth ===")
print(youtube.followers_growth_analysis)

print("\n=== Engagement Performance ===")
print(youtube.growth_performance_analysis)

summary = result["summary_result"]
print("===============SUMMARY RESULT ==========")
print("===========================================")
print("SUMMARY ANALYSIS")
print(summary.summary_result)