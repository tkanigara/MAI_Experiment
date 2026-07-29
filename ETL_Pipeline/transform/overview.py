from abc import ABC, abstractmethod
import pandas as pd


class BaseOverviewProcessor(ABC):
    def __init__(
        self,
        followers_df: pd.DataFrame,
        engagement_df: pd.DataFrame,
        client_name: str,
        platform: str,
    ):
        self.followers_df = followers_df.copy()
        self.engagement_df = engagement_df.copy()
        self.client_name = client_name
        self.platform = platform

    @abstractmethod
    def run(self) -> pd.DataFrame:
        pass

class InstagramOverviewProcessor(
    BaseOverviewProcessor
):

    def _latest_followers(self):

        latest_period = (
            self.followers_df[
                ["year", "month"]
            ]
            .drop_duplicates()
            .sort_values(
                ["year", "month"]
            )
            .tail(1)
        )

        year = latest_period.iloc[0]["year"]
        month = latest_period.iloc[0]["month"]

        return self.followers_df[
            (self.followers_df["year"] == year)
            &
            (self.followers_df["month"] == month)
        ]

    def _latest_engagement(self):

        latest_period = (
            self.engagement_df
            [["year", "month"]]
            .drop_duplicates()
            .sort_values(
                ["year", "month"],
                ascending=True
            )
            .tail(1)
        )

        year = latest_period.iloc[0]["year"]
        month = latest_period.iloc[0]["month"]

        return self.engagement_df[
            (self.engagement_df["year"] == year)
            &
            (self.engagement_df["month"] == month)
        ]

    def run(self):

        followers = self._latest_followers()

        engagement = self._latest_engagement()

        rows = []

        latest_period = (
            engagement[
                ["year", "month"]
            ]
            .drop_duplicates()
            .iloc[0]
        )

        scrapped_at = pd.Timestamp(
            year=int(latest_period["year"]),
            month=int(latest_period["month"]),
            day=1
        )

        for _, row in followers.iterrows():

            rows.append({
                "client": self.client_name,
                "platform": self.platform,
                "scrapped_at": scrapped_at,
                "category": "followers",
                "metric": row["metric"],
                "value": row["value"]
            })

        interaction_metrics = [
            "total_engagement",
            "likes",
            "comments",
            "shares",
            "reach",
            "er"
        ]

        content_metrics = [
            "number_of_post"
        ]

        for _, row in engagement.iterrows():

            metric = row["metric"]

            if metric in interaction_metrics:

                category = "interaction"

            elif metric in content_metrics:

                category = "content"

            else:
                continue

            rows.append({
                "client": self.client_name,
                "platform": self.platform,
                "scrapped_at": scrapped_at,
                "category": category,
                "metric": metric,
                "value": row["value"]
            })

        return pd.DataFrame(rows)

OVERVIEW_PROCESSOR = {
    "instagram": InstagramOverviewProcessor
}