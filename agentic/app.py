from workflows.socmed_workflow.graph import app
from workflows.socmed_workflow.state import (
    State,
    Request, 
    instagram_result_analysis, facebook_result_analysis, tiktok_result_analysis, youtube_result_analysis, 
    linkedin_result_analysis
)
from datetime import date

initial_state = State(
    # request=Request(
    #     user_intent="Generate Marketing Report",
    #     client_code="mai001",
    #     report_date=date(2026, 6, 8),
    #     generate_slides=False,
    # )
        request=Request(
        user_intent="Generate Marketing Report",
        client_code="mai001",
        report_date=date(2026, 6, 23),
        generate_slides=False,
        slides_dry_run=False,
        persist_insights=False,
        reuse_cached_insights=False,
    ),
)

result = app.invoke(initial_state)


retrieval_data = result["Metadata"]
print(retrieval_data)
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

print("\n=== Top Performing Content ===")
print(instagram.top_content_performance)

print("============= Low Content ===========")
print(instagram.low_content_performance)

print("\n=== Competitor Analysis ===")
print(instagram.competitor_analysis)

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

print("\n=== Top Performing Content ===")
print(facebook.top_content_performance)

print("============= Low Content ===========")
print(facebook.low_content_performance)

print("\n=== Competitor Analysis ===")
print(facebook.competitor_analysis)

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

print("\n=== Top Performing Content ===")
print(tiktok.top_content_performance)

print("============= Low Content ===========")
print(tiktok.low_content_performance)

print("\n=== Competitor Analysis ===")
print(tiktok.competitor_analysis)

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

print("\n=== Top Performing Content ===")
print(youtube.top_content_performance)

print("============= Low Content ===========")
print(youtube.low_content_performance)


print("\n=== Competitor Analysis ===")
print(youtube.competitor_analysis)

linkedin = result["linkedin_result"]
print("===============LINKEDIN ANALYSIS RESULT ==========")
print("===========================================")
print("=== KPI Analysis ===")
print(linkedin.kpi_analysis)

print("\n=== Social Media Overview ===")
print(linkedin.socmed_overview_analysis)

print("\n=== Followers Growth ===")
print(linkedin.followers_growth_analysis)

print("\n=== Engagement Performance ===")
print(linkedin.growth_performance_analysis)

print("\n=== Top Performing Content ===")
print(linkedin.top_content_performance)

print("============= Low Content ===========")
print(linkedin.low_content_performance)

print("\n=== Competitor Analysis ===")
print(linkedin.competitor_analysis)

print("\n =========== ALL SOCIAL MEDIA PERFORMANCE =======")
all_socmed = result["summary_all_socmed"]
print(all_socmed.summary)

print("===============PLATFORM SUMMARIES ==========")
for platform, field_name in (
    ("Instagram", "summary_instagram"),
    ("Facebook", "summary_facebook"),
    ("TikTok", "summary_tiktok"),
    ("YouTube", "summary_youtube"),
    ("LinkedIn", "summary_linkedin"),
):
    summary = result[field_name]
    print(f"\n=== {platform} ===")
    print("Key summary:", summary.key_summary)
    print("Action plan:", summary.action_plan)

generation = result["report_generation"]
print("===============REPORT GENERATION ==========")
print("STATUS:", generation.status)
print("URL:", generation.presentation_url)
print("ERROR:", generation.error)
print("ANALYSIS CACHE HIT:", result["analysis_cache_hit"])
