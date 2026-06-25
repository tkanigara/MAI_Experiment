from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Type
import pandas as pd

class OutputCol:
    CLIENT_ID  = "client_id"
    PLATFORM   = "platform"
    YEAR       = "year"
    MONTH      = "month"
    METRIC     = "metric"
    VALUE      = "value"

class MetricName:
    NUM_POST          = "number_of_post"
    IMPRESSIONS       = "impressions"
    REACH             = "reach"
    LIKES             = "likes"
    COMMENTS          = "comments"
    SHARES            = "shares"
    TOTAL_ENGAGEMENT  = "total_engagement"
    ER                = "er"

@dataclass
class EngagementColumnConfig:
    date_col              : str
    impressions_col       : str
    reach_col             : str
    likes_col             : str
    comments_col          : str
    shares_col            : str
    extra_engagement_cols : List[str] = field(default_factory=list)
    extra_sum_cols        : List[str] = field(default_factory=list)

PLATFORM_COLUMN_CONFIG: Dict[str, EngagementColumnConfig] = {
    "instagram": EngagementColumnConfig(
        date_col              = "timestamp",
        impressions_col       = "insight_views",
        reach_col             = "insight_reach",
        likes_col             = "insight_likes",
        comments_col          = "insight_comments",
        shares_col            = "insight_shares",
        extra_engagement_cols = ["insight_saved"], 
        extra_sum_cols        = [],
    ),

    # ── TikTok ────────────────────────────────────────────────────
    # TODO: sesuaikan nama kolom dengan raw CSV TikTok kamu
    # "tiktok": EngagementColumnConfig(
    #     date_col              = "date",
    #     impressions_col       = "video_views",
    #     reach_col             = "video_views",
    #     likes_col             = "likes",
    #     comments_col          = "comments",
    #     shares_col            = "shares",
    #     extra_engagement_cols = [],
    #     extra_sum_cols        = [],
    # ),

    # ── Facebook ──────────────────────────────────────────────────
    # TODO: sesuaikan nama kolom dengan raw CSV Facebook kamu
    # "facebook": EngagementColumnConfig(
    #     date_col              = "date",
    #     impressions_col       = "impressions",
    #     reach_col             = "reach",
    #     likes_col             = "reactions",
    #     comments_col          = "comments",
    #     shares_col            = "shares",
    #     extra_engagement_cols = ["clicks"],
    #     extra_sum_cols        = [],
    # ),

    # ── YouTube ───────────────────────────────────────────────────
    # TODO: sesuaikan nama kolom dengan raw CSV YouTube kamu
    # "youtube": EngagementColumnConfig(
    #     date_col              = "date",
    #     impressions_col       = "views",
    #     reach_col             = "views",
    #     likes_col             = "likes",
    #     comments_col          = "comments",
    #     shares_col            = "shares",
    #     extra_engagement_cols = [],
    #     extra_sum_cols        = ["watch_time_hours"],
    # ),

}

class BaseMetricDefinition(ABC):

    @staticmethod
    @abstractmethod
    def total_engagement(
        df: pd.DataFrame,
        cfg: EngagementColumnConfig,
    ) -> pd.Series:
        """
        Hitung total_engagement per baris SEBELUM agregasi bulanan.
        Hasilnya akan di-SUM saat groupby bulan.
        """
        ...

    @staticmethod
    @abstractmethod
    def er(
        df: pd.DataFrame,
        cfg: EngagementColumnConfig,
    ) -> pd.Series:
        """
        Hitung ER (%) per baris SETELAH agregasi bulanan.
        df sudah berisi kolom dengan nama dari MetricName.*.
        """
        ...

    @staticmethod
    def extra_metrics() -> List[str]:
        """
        Opsional. Kembalikan list MetricName.* tambahan yang ingin
        disertakan di output long format.
        Default: tidak ada metric tambahan.
        """
        return []
    
class InstagramMetricDefinition(BaseMetricDefinition):
    """
    Instagram Formula

    Total Engagement =
        Likes + Comments + Shares

    ER =
        Total Engagement / Reach * 100
    """

    @staticmethod
    def total_engagement(
        df: pd.DataFrame,
        cfg: EngagementColumnConfig,
    ) -> pd.Series:

        return (
            df[cfg.likes_col]
            + df[cfg.comments_col]
            + df[cfg.shares_col]
        )

    @staticmethod
    def er(
        df: pd.DataFrame,
        cfg: EngagementColumnConfig,
    ) -> pd.Series:

        reach = df[MetricName.REACH].replace(0, pd.NA)

        return (
            df[MetricName.TOTAL_ENGAGEMENT]
            / reach
            * 100
        ).round(2)

# ── Template platform baru — uncomment & sesuaikan ────────────────

# class TikTokMetricDefinition(BaseMetricDefinition):
#     @staticmethod
#     def total_engagement(df, cfg):
#         cols = [cfg.likes_col, cfg.comments_col, cfg.shares_col]
#         return df[cols].sum(axis=1)
#
#     @staticmethod
#     def er(df, cfg):
#         reach = df[MetricName.REACH].replace(0, pd.NA)
#         return (df[MetricName.TOTAL_ENGAGEMENT] / reach * 100).round(2)


# class FacebookMetricDefinition(BaseMetricDefinition):
#     @staticmethod
#     def total_engagement(df, cfg):
#         cols = (
#             [cfg.likes_col, cfg.comments_col, cfg.shares_col]
#             + [c for c in cfg.extra_engagement_cols if c in df.columns]
#         )
#         return df[cols].sum(axis=1)
#
#     @staticmethod
#     def er(df, cfg):
#         reach = df[MetricName.REACH].replace(0, pd.NA)
#         return (df[MetricName.TOTAL_ENGAGEMENT] / reach * 100).round(2)


# class YouTubeMetricDefinition(BaseMetricDefinition):
#     @staticmethod
#     def total_engagement(df, cfg):
#         cols = [cfg.likes_col, cfg.comments_col, cfg.shares_col]
#         return df[cols].sum(axis=1)
#
#     @staticmethod
#     def er(df, cfg):
#         reach = df[MetricName.REACH].replace(0, pd.NA)
#         return (df[MetricName.TOTAL_ENGAGEMENT] / reach * 100).round(2)

class BaseEngagementPerformanceProcessor(ABC):
    PLATFORM : str                        = ""
    METRIC   : Type[BaseMetricDefinition] = None

    def __init__(
        self,
        media_df   : pd.DataFrame,
        client_name: str,
    ) -> None:
        if not self.PLATFORM:
            raise NotImplementedError("Set atribut PLATFORM di subclass.")
        if self.METRIC is None:
            raise NotImplementedError("Set atribut METRIC di subclass.")

        self.media_df    = media_df.copy()
        self.client_name = client_name
        self.config      = PLATFORM_COLUMN_CONFIG[self.PLATFORM]

    def run(self) -> pd.DataFrame:
        if self.media_df.empty:
            return pd.DataFrame()

        df = self._validate_columns(self.media_df)
        if df.empty:
            return pd.DataFrame()

        df = self._parse_types(df)
        if df.empty:
            return pd.DataFrame()

        df = self._compute_pre_agg_metrics(df)
        df = self._aggregate_by_month(df)
        df = self._rename_to_metric_cols(df)
        df = self._compute_post_agg_metrics(df)
        df = self._melt_to_long_format(df)
        df = self._add_id_cols(df)
        df = self._reorder_output_columns(df)
        return df

    def _validate_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg      = self.config
        required = [
            cfg.date_col, cfg.impressions_col, cfg.reach_col,
            cfg.likes_col, cfg.comments_col,   cfg.shares_col,
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            print(
                f"[EngagementPerformance][{self.PLATFORM}] "
                f"Kolom tidak ditemukan: {missing}"
            )
            return pd.DataFrame()
        return df
    
    def _parse_types(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.config

        df[cfg.date_col] = pd.to_datetime(
            df[cfg.date_col], errors="coerce"
        )
        df = df.dropna(subset=[cfg.date_col])
        if df.empty:
            print(
                f"[EngagementPerformance][{self.PLATFORM}] "
                f"Semua baris '{cfg.date_col}' gagal di-parse."
            )
            return pd.DataFrame()

        if df[cfg.date_col].dt.tz is not None:
            df[cfg.date_col] = df[cfg.date_col].dt.tz_localize(None)

        df["_month_period"] = df[cfg.date_col].dt.to_period("M")

        numeric_cols = (
            [cfg.impressions_col, cfg.reach_col,
             cfg.likes_col, cfg.comments_col, cfg.shares_col]
            + cfg.extra_engagement_cols
            + cfg.extra_sum_cols
        )
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col], errors="coerce"
                ).fillna(0)

        return df

    def _compute_pre_agg_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        df["_total_engagement_raw"] = self.METRIC.total_engagement(
            df, self.config
        )
        return df

    def _aggregate_by_month(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.config
        grouped = (
            df.groupby("_month_period")
            .agg(
                impressions=(
                    cfg.impressions_col,
                    "sum"
                ),

                reach=(
                    cfg.reach_col,
                    "sum"
                ),

                likes=(
                    cfg.likes_col,
                    "sum"
                ),

                comments=(
                    cfg.comments_col,
                    "sum"
                ),

                shares=(
                    cfg.shares_col,
                    "sum"
                ),

                total_engagement=(
                    "_total_engagement_raw",
                    "sum"
                ),

                number_of_post=(
                    cfg.date_col,
                    "count"
                )
            )
            .reset_index()
        )

        return grouped
    
    def _rename_to_metric_cols(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        rename_map = {
            "impressions": MetricName.IMPRESSIONS,
            "reach": MetricName.REACH,
            "likes": MetricName.LIKES,
            "comments": MetricName.COMMENTS,
            "shares": MetricName.SHARES,
            "total_engagement": MetricName.TOTAL_ENGAGEMENT,
            "number_of_post": MetricName.NUM_POST,
        }

        return df.rename(columns=rename_map)

    def _compute_post_agg_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        df[MetricName.ER] = self.METRIC.er(df, self.config)
        return df

    def _melt_to_long_format(self, df: pd.DataFrame) -> pd.DataFrame:
        base_metrics = [
            MetricName.NUM_POST,
            MetricName.IMPRESSIONS,
            MetricName.REACH,
            MetricName.LIKES,
            MetricName.COMMENTS,
            MetricName.SHARES,
            MetricName.TOTAL_ENGAGEMENT,
            MetricName.ER,
        ]

        extra = [
            m for m in self.METRIC.extra_metrics()
            if m in df.columns and m not in base_metrics
        ]
        metric_cols = [m for m in base_metrics if m in df.columns] + extra

        long_df = df.melt(
            id_vars   = ["_month_period"],
            value_vars = metric_cols,
            var_name  = OutputCol.METRIC,
            value_name = OutputCol.VALUE,
        )
        return long_df

    def _add_id_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        df[OutputCol.CLIENT_ID] = self.client_name
        df[OutputCol.PLATFORM]  = self.PLATFORM
        df[OutputCol.YEAR]      = (
            df["_month_period"].dt.year.astype(int)
        )
        df[OutputCol.MONTH]     = (
            df["_month_period"].dt.month.astype(int)
        )
        return df

    def _reorder_output_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = [
            OutputCol.CLIENT_ID,
            OutputCol.PLATFORM,
            OutputCol.YEAR,
            OutputCol.MONTH,
            OutputCol.METRIC,
            OutputCol.VALUE,
        ]
        return df[[c for c in cols if c in df.columns]]

class InstagramEngagementPerformanceProcessor(
    BaseEngagementPerformanceProcessor
):
    PLATFORM = "instagram"
    METRIC   = InstagramMetricDefinition


# ── Template platform baru ─────────────────────────────────────────

# class TikTokEngagementPerformanceProcessor(
#     BaseEngagementPerformanceProcessor
# ):
#     PLATFORM = "tiktok"
#     METRIC   = TikTokMetricDefinition


# class FacebookEngagementPerformanceProcessor(
#     BaseEngagementPerformanceProcessor
# ):
#     PLATFORM = "facebook"
#     METRIC   = FacebookMetricDefinition


# class YouTubeEngagementPerformanceProcessor(
#     BaseEngagementPerformanceProcessor
# ):
#     PLATFORM = "youtube"
#     METRIC   = YouTubeMetricDefinition

ENGAGEMENT_PERFORMANCE_PROCESSOR: Dict[
    str, Type[BaseEngagementPerformanceProcessor]
] = {
    "instagram" : InstagramEngagementPerformanceProcessor,
    # "tiktok"  : TikTokEngagementPerformanceProcessor,
    # "facebook": FacebookEngagementPerformanceProcessor,
    # "youtube" : YouTubeEngagementPerformanceProcessor,
}

class EngagementPerformanceSheetFormatter:
    """
    Memastikan output engagement performance
    sesuai format sheet:

    client_id | platform | year | month | metric | value
    """

    OUTPUT_COLUMNS = [
        OutputCol.CLIENT_ID,
        OutputCol.PLATFORM,
        OutputCol.YEAR,
        OutputCol.MONTH,
        OutputCol.METRIC,
        OutputCol.VALUE,
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def run(self) -> pd.DataFrame:

        if self.df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        result = self.df.copy()

        # pastikan kolom ada
        for col in self.OUTPUT_COLUMNS:
            if col not in result.columns:
                result[col] = None

        result = result[self.OUTPUT_COLUMNS]

        result = result.sort_values(
            by=[
                OutputCol.CLIENT_ID,
                OutputCol.PLATFORM,
                OutputCol.YEAR,
                OutputCol.MONTH,
                OutputCol.METRIC,
            ]
        ).reset_index(drop=True)

        return result