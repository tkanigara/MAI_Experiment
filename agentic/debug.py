from tools.retrieval import retrieve_social_performance
from datetime import date

ig = retrieve_social_performance.invoke({
    "platform": "instagram",
    "client_code": "mai001",
    "report_date": "2026-07-08"
})

fb = retrieve_social_performance.invoke({
    "platform": "facebook",
    "client_code": "mai001",
    "report_date": "2026-07-08"
})

tt =retrieve_social_performance.invoke({
    "platform": "tiktok",
    "client_code": "mai001",
    "report_date":"2026-07-08"
})

yt = retrieve_social_performance.invoke({
    "platform": "youtube",
    "client_code": "mai001",
    "report_date": "2026-07-08"
})

print("=============== INSTAGRAM ===============")
print(f"{ig}\n")

print("=============== YOUTUBE ===============")
print(f"{yt}\n")

print("=============== TIKTOK ===============")
print(f"{tt}\n")

print("=============== FACEBOOK ===============")
print(f"{fb}\n")

