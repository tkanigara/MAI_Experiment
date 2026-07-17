from pprint import pprint

from tools.retrieva_ig_data import (
    retrieve_top_performing_content,
    retrieve_content_by_bucket,
)

client_code = "mai001"
platform = "instagram"
report_date = "2026-07-08"

print("=" * 80)
print("TOP PERFORMING CONTENT (OLD TOOL)")
print("=" * 80)

top_old = retrieve_top_performing_content.invoke(
    {
        "client_code": client_code,
        "report_date": report_date,
        "platform": platform,
    }
)

pprint(top_old)

print("\n" + "=" * 80)
print("TOP PERFORMING CONTENT (NEW TOOL)")
print("=" * 80)

top_new = retrieve_content_by_bucket.invoke(
    {
        "client_code": client_code,
        "report_date": report_date,
        "platform": platform,
        "bucket": "top",
    }
)

pprint(top_new)
