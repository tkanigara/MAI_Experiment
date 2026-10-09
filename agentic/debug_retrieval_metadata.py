from pprint import pprint

from tools.tools_list_ads_creative.retrieval_metadata import retrieve_creative_metadata

request = {
    "client_code": "jba",
    "period_id": "2026-08-01",
    "analysis_type": "creative",
    "platforms": [
        "instagram",
        "facebook",
    ],
    "objectives": [
        "reach",
        "link_clicks",
        "leads",
    ],
    "campaign_ids": [],
    "adset_ids": [],
    "include_breakdowns": True,
}


def main():
    print("=" * 60)
    print("DEBUG: RETRIEVE CREATIVE METADATA")
    print("=" * 60)

    print("\n[REQUEST]")
    pprint(request)

    print("\n[INPUT TO TOOL]")
    tool_input = {
        "client_code": request["client_code"],
        "period_id": request["period_id"],
    }
    pprint(tool_input)

    print("\n[RUNNING TOOL...]")

    try:
        result = retrieve_creative_metadata.invoke(tool_input)

        print("\n[SUCCESS]")
        print("=" * 60)
        pprint(result)

        print("\n[METADATA]")
        print("=" * 60)

        for key, value in result.items():
            print(f"{key}: {value}")

    except Exception as e:
        print("\n[ERROR]")
        print("=" * 60)
        print(f"Type    : {type(e).__name__}")
        print(f"Message : {e}")

        raise


if __name__ == "__main__":
    main()