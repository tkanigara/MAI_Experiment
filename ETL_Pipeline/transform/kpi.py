from __future__ import annotations
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from abc import ABC, abstractmethod
from typing import Optional

class BaseKPIProcessor(ABC):
    def __init__(
        self,
        overview_df: pd.DataFrame,
        followers_df: pd.DataFrame,
        engagement_df: pd.DataFrame,
        target_df: pd.DataFrame,
        client_name: str,
        platform: str,
    ):
        self.overview_df = overview_df.copy()
        self.followers_df = followers_df.copy()
        self.engagement_df = engagement_df.copy()
        self.target_df = target_df.copy()
        self.client_name = client_name
        self.platform = platform

    @abstractmethod
    def run(self) -> pd.DataFrame:
        pass

class InstagramKPIProcessor(BaseKPIProcessor):

    KPI_MAPPING = {
        "followers": "net_growth",
        "engagement": "total_engagement",
        "reach": "reach",
    }

    def _latest_period(self):

        latest = (
            self.overview_df[
                ["scrapped_at"]
            ]
            .drop_duplicates()
            .sort_values("scrapped_at")
            .tail(1)
        )

        return latest.iloc[0]["scrapped_at"]

    def _get_target(self, metric):
        if self.target_df.empty:
            return 0, 0

        required_cols = [
            "client",
            "platform",
            "metric",
            "target_month",
            "target_year"
        ]

        if not all(
            col in self.target_df.columns
            for col in required_cols
        ):
            return 0, 0

        row = self.target_df[
            (self.target_df["client"] == self.client_name)
            &
            (self.target_df["platform"] == self.platform)
            &
            (self.target_df["metric"] == metric)
        ]

        if row.empty:
            return 0, 0

        return (
            float(row.iloc[0]["target_month"]),
            float(row.iloc[0]["target_year"])
        )
    def _get_current_month(self, metric):
        source_metric = self.KPI_MAPPING[metric]
        latest_period = self._latest_period()

        row = self.overview_df[
            (self.overview_df["metric"] == source_metric)
            &
            (
                pd.to_datetime(
                    self.overview_df["scrapped_at"]
                )
                ==
                pd.to_datetime(latest_period)
            )
        ]

        print(
            f"[KPI] Metric: {source_metric}"
        )

        print(row)
        if row.empty:
            return 0

        value = pd.to_numeric(
            row.iloc[0]["value"],
            errors="coerce"
        )

        return 0 if pd.isna(value) else float(value)
    def _get_current_year(self, metric):

        source_metric = (
            self.KPI_MAPPING[metric]
        )

        if metric == "followers":

            row = self.followers_df[
                self.followers_df["metric"]
                == source_metric
            ]

        else:

            row = self.engagement_df[
                self.engagement_df["metric"]
                == source_metric
            ]

        if row.empty:
            return 0

        return (
            pd.to_numeric(
                row["value"],
                errors="coerce"
            )
            .fillna(0)
            .sum()
        )

    def run(self):

        rows = []

        scrapped_at = (
            self._latest_period()
        )

        for metric in self.KPI_MAPPING.keys():

            target_month, target_year = (
                self._get_target(metric)
            )

            current_month = (
                self._get_current_month(metric)
            )

            current_year = (
                self._get_current_year(metric)
            )

            achievement_month = (
                (current_month / target_month) * 100
                if target_month
                else 0
            )

            achievement_year = (
                (current_year / target_year) * 100
                if target_year
                else 0
            )

            rows.append(
                {
                    "client": self.client_name,
                    "platform": self.platform,
                    "scrapped_at": scrapped_at,
                    "metric": metric,
                    "target_month": round(target_month, 2),
                    "current_month": round(current_month, 2),
                    "achievement_month": round(
                        achievement_month,
                        2
                    ),
                    "target_year": round(target_year, 2),
                    "current_year": round(current_year, 2),
                    "achievement_year": round(
                        achievement_year,
                        2
                    ),
                }
            )

        return pd.DataFrame(rows)

KPI_PROCESSOR = {"instagram": InstagramKPIProcessor}

