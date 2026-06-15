from __future__ import annotations
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from abc import ABC, abstractmethod
from typing import Optional

class BaseKPIProcessor(ABC):
    column_map: dict[str, str] = {}
    required_column: list[str] = []

    @abstractmethod
    def generate_kpi(self) -> pd.DataFrame:
        pass

#SOCIAL MEDIA TRANSFORMER
class InstagramKPIProcessor(BaseKPIProcessor):

    KPI_CONFIG = {
        "Followers": {
            "source": "account",
            "type": "single",
            "column": "followers_count"
        },

        "Reach": {
            "source": "media",
            "type": "sum",
            "column": "insight_reach"
        },

        "Engagement": {
            "source": "media",
            "type": "sum",
            "column": "insight_total_interactions"
        }
    }

    def __init__(self, account_df, media_df):
        self.account_df = account_df
        self.media_df = media_df

    def get_metadata(self):

        if not self.account_df.empty:
            source = self.account_df

        elif not self.media_df.empty:
            source = self.media_df

        else:
            raise ValueError("No DataFrame Available")

        return {
            "client": source["client"].iloc[0],
            "platform": source["platform"].iloc[0],
            "scrapped_at": source["scrapped_at"].iloc[0]
        }

    def generate_kpi(self):
        meta = self.get_metadata()
        rows = []
        for metric, config in self.KPI_CONFIG.items():
            current_value = 0
            source_df = (
                self.account_df
                if config["source"] == "account"
                else self.media_df
            )

            if source_df.empty:
                continue

            if config["type"] == "single":

                current_value = (
                    source_df[config["column"]]
                    .iloc[0]
                )

            elif config["type"] == "sum":

                current_value = (
                    source_df[config["column"]]
                    .fillna(0)
                    .sum()
                )

            rows.append(
                {
                    "client": meta["client"],
                    "platform": meta["platform"],
                    "scrapped_at": meta["scrapped_at"],
                    "metric": metric,
                    "target_month": None,
                    "current_month": current_value,
                    "achievement_month": None,
                    "target_year": None,
                    "current_year": current_value,
                    "achievement_year": None
                }
            )

        return pd.DataFrame(rows)

class KPIProcessorFactory:
    registry = {
        "instagram":InstagramKPIProcessor
    }

    @classmethod
    def get(cls, platform: str, account_df: pd.DataFrame, media_df: pd.DataFrame):
        key = platform.strip().lower()
        processor_cls = cls.registry.get(key)

        if processor_cls is None:
            raise ValueError(
                f"KPI Processor for {platform} not available"
            )
        return processor_cls(
        account_df,
        media_df
        )
#Class ini sementara taroh sini dulu, nanti bakal taroh di load phase, dan class ini harus bisa capable handle semua komponen
class GSpreadWritter:
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
    
    def write(self, df:pd.DataFrame, sheet_name: str, mode: str = "replace"):
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name, rows=str(len(df) + 10), cols=str(len(df.columns) + 5)
            )
        
        if mode == "replace":
            worksheet.clear()
            set_with_dataframe(worksheet, df, include_index=False, include_column_header=True)
        
        elif mode == "append":
            existing = worksheet.get_all_values()
            start_row = len(existing) + 1
            if start_row == 1:
                set_with_dataframe(worksheet, df, include_index=False, include_column_header=True)
            else:
                set_with_dataframe(
                    worksheet, df, row=start_row,
                    include_index=False, include_column_header=False
                )
        else:
            raise ValueError(f"Mode Unrecognized: {mode}")
        print(f"[GSpreadWriter] succesfully write to sheet {sheet_name} (mode={mode})")

class KPIProcessor:
    def __init__(self, account_df: pd.DataFrame, media_df: pd.DataFrame, gspread_writer: Optional[GSpreadWritter] =None):
        self.account_df = account_df
        self.media_df = media_df
        self.writter = gspread_writer

    def generate(self):
        if not self.account_df.empty:
            platform = (
                self.account_df["platform"]
                .iloc[0]
            )
        elif not self.media_df.empty:
            platform = (
                self.media_df["platform"]
                .iloc[0]
            )
        else:
            return pd.DataFrame()

        processor = KPIProcessorFactory.get(
            platform=platform,
            account_df=self.account_df,
            media_df=self.media_df
        )
        return processor.generate_kpi()
        
    def process_and_export(
        self,
        sheet_name: str,
        mode: str = "replace"
    ):

        result_df = self.generate()

        if result_df.empty:

            print(
                "[KPIProcessor] Tidak ada data untuk diekspor."
            )

            return result_df

        if self.writer:

            self.writter.write(
                result_df,
                sheet_name=sheet_name,
                mode=mode
            )

        return result_df