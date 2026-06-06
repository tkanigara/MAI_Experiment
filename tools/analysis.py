import pandas as pd

def analyze_client_data(data):
    """
    Simple Analysis
    """
    results = {}
    for client_name, df in data.items():

        result = {
            "total_posts": 0,
            "platform_performance": {},
            "top_content": [],
            "low_content": []
        }
        result["total_posts"] = len(df)
        if "platform" in df.columns:

            platform_stats = (
                df.groupby("platform")
                .size()
                .sort_values(ascending=False)
            )

            result["platform_performance"] = (
                platform_stats.to_dict()
            )

        engagement_cols = [
            col
            for col in [
                "likes",
                "comments",
                "shares",
                "views"
            ]
            if col in df.columns
        ]

        if engagement_cols:

            df["engagement_score"] = (
                df[engagement_cols]
                .fillna(0)
                .sum(axis=1)
            )

            top_posts = (
                df.sort_values(
                    "engagement_score",
                    ascending=False
                )
                .head(3)
            )

            result["top_content"] = (
                top_posts.to_dict(
                    orient="records"
                )
            )

            # Bottom 3 Content

            low_posts = (
                df.sort_values(
                    "engagement_score",
                    ascending=True
                )
                .head(3)
            )

            result["low_content"] = (
                low_posts.to_dict(
                    orient="records"
                )
            )

        results[client_name] = result

    return results