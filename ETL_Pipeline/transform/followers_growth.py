import pandas as pd
import gspread
from dateutil.relativedelta import relativedelta
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from datetime import datetime

class FollowersGrowthBase:
    DATA_KIND   = "account"
    DATE_COLUMN = "Month"
    DATE_FORMAT = "%b %Y"

    CSV_COLUMNS: list[str]            = []
    METRICS: dict[str, callable]      = {}

    def __init__(self, df: pd.DataFrame):
        self.df = df[df["data_kind"] == self.DATA_KIND].copy()

    def _parse_period(self, value: str) -> tuple[int, int]:
        dt = pd.to_datetime(value, format=self.DATE_FORMAT)
        return dt.year, dt.month

    def _extract_csv_values(self, row: pd.Series) -> dict[str, float]:
        result = {}
        for col in self.CSV_COLUMNS:
            if col not in row.index:
                print(f"  Warning: kolom '{col}' tidak ditemukan.")
                result[col] = None
            else:
                result[col] = pd.to_numeric(
                    str(row[col]).replace(",", ""), errors="coerce"
                )
        return result

    def _compute_metrics(self, csv_values: dict) -> list[dict]:
        records = []
        for metric_name, fn in self.METRICS.items():
            try:
                value = fn(csv_values)
            except Exception as e:
                print(f"  Warning: metric '{metric_name}' gagal dihitung: {e}")
                value = None
            records.append({"metric": metric_name, "value": value})
        return records

    def _to_long_format(self) -> pd.DataFrame:
        records = []

        for _, row in self.df.iterrows():
            period_raw = row.get(self.DATE_COLUMN)
            if pd.isna(period_raw) or str(period_raw).strip() == "":
                continue

            try:
                year, month = self._parse_period(str(period_raw).strip())
            except Exception as e:
                print(f"  Skipping row, cannot parse date '{period_raw}': {e}")
                continue

            base = {
                "client_id": row["client"],
                "platform":  row["platform"],
                "year":      year,
                "month":     month,
            }

            csv_values = self._extract_csv_values(row)

            for metric in self._compute_metrics(csv_values):
                records.append({**base, **metric})

        return pd.DataFrame(records)

    def run(self) -> pd.DataFrame:
        if self.df.empty:
            print(f"[{self.__class__.__name__}] Tidak ada data.")
            return pd.DataFrame()

        result = self._to_long_format()
        print(f"[{self.__class__.__name__}] Total → {len(result)} rows")
        return result

class FollowersGrowthMetricProcessor:

    def __init__(
        self,
        current_df: pd.DataFrame,
        historical_df: pd.DataFrame
    ):
        self.current_df = current_df.copy()
        self.historical_df = historical_df.copy()

    def calculate_net_growth(self) -> pd.DataFrame:

        followers_df = self.current_df[
            self.current_df["metric"] == "total_followers"
        ].copy()

        if followers_df.empty:
            return pd.DataFrame()

        results = []

        for _, row in followers_df.iterrows():

            current_year = int(row["year"])
            current_month = int(row["month"])

            current_date = datetime(
                current_year,
                current_month,
                1
            )

            previous_date = (
                current_date
                - relativedelta(months=1)
            )

            prev_row = self.historical_df[
                (self.historical_df["client_id"] == row["client_id"])
                &
                (self.historical_df["platform"] == row["platform"])
                &
                (pd.to_numeric(
                    self.historical_df["year"],
                    errors="coerce"
                ) == previous_date.year)
                &
                (pd.to_numeric(
                    self.historical_df["month"],
                    errors="coerce"
                ) == previous_date.month)
                &
                (self.historical_df["metric"] == "total_followers")
            ]

            print(
                f"Searching previous period: "
                f"{previous_date.year}-{previous_date.month}"
            )

            print(prev_row)

            if prev_row.empty:

                net_growth = 0

            else:

                previous_followers = pd.to_numeric(
                    prev_row.iloc[0]["value"],
                    errors="coerce"
                )

                current_followers = pd.to_numeric(
                    row["value"],
                    errors="coerce"
                )

                net_growth = (
                    current_followers
                    - previous_followers
                )

            results.append({
                "client_id": row["client_id"],
                "platform": row["platform"],
                "year": current_year,
                "month": current_month,
                "metric": "net_growth",
                "value": net_growth
            })

        return pd.DataFrame(results)
    
    def calculate_unfollows(self, growth_df: pd.DataFrame) -> pd.DataFrame:
        follows_df = self.current_df[
            self.current_df["metric"] == "follows"
        ].copy()

        if follows_df.empty or growth_df.empty:
            return pd.DataFrame()

        growth_lookup = growth_df.rename(
            columns={"value": "net_growth"}
        )[
            [
                "client_id",
                "platform",
                "year",
                "month",
                "net_growth"
            ]
        ]

        merged = follows_df.merge(
            growth_lookup,
            on=[
                "client_id",
                "platform",
                "year",
                "month"
            ],
            how="left"
        )

        merged["value"] = (
            pd.to_numeric(
                merged["value"],
                errors="coerce"
            )
            -
            pd.to_numeric(
                merged["net_growth"],
                errors="coerce"
            )
        )

        return pd.DataFrame({
            "client_id": merged["client_id"],
            "platform": merged["platform"],
            "year": merged["year"],
            "month": merged["month"],
            "metric": "unfollows",
            "value": merged["value"]
        })
    
    def run(self) -> pd.DataFrame:

        growth_df = self.calculate_net_growth()
        unfollows_df = self.calculate_unfollows(growth_df)
        if growth_df.empty:
            return self.current_df

        return pd.concat(
            [
                self.current_df,
                growth_df,
                unfollows_df
            ],
            ignore_index=True
        )
    
class InstagramFollowersGrowth(FollowersGrowthBase):
    DATE_COLUMN = "report_month"
    DATE_FORMAT = "%Y-%m"
 
    CSV_COLUMNS = [
        "followers_count",
        "follows_count",
    ]
 
    METRICS = {
        "total_followers": lambda c: c["followers_count"],
        "follows":         lambda c: c["follows_count"],
        # Net growth tidak bisa dihitung dari 1 baris snapshot,
        # perlu dibandingkan antar snapshot — tambahkan jika sudah ada kolom selisihnya
        # "follow_rate":  lambda c: c["follows_count"] / c["followers_count"] * 100,
    }

#class tiktok
#class youtube
#class facebook

FOLLOWERS_GROWTH_PROCESSOR = {
    "instagram": InstagramFollowersGrowth
}
class GSpreadWriter:
    def __init__(
        self,
        credentials_path: str,
        spreadsheet_id: str
    ):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes
        )

        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(
            spreadsheet_id
        )

    def write(
        self,
        df: pd.DataFrame,
        sheet_name: str,
        mode: str = "replace"
    ):

        if df.empty:
            print(
                f"[GSpreadWriter] Skip '{sheet_name}' "
                f"(empty dataframe)"
            )
            return

        try:
            worksheet = self.spreadsheet.worksheet(
                sheet_name
            )

        except gspread.exceptions.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=str(max(len(df) + 100, 1000)),
                cols=str(max(len(df.columns) + 10, 20))
            )

        if mode == "replace":
            worksheet.clear()
            set_with_dataframe(
                worksheet,
                df,
                include_index=False,
                include_column_header=True,
                resize=True
            )

        elif mode == "append":
            existing = worksheet.get_all_values()
            start_row = len(existing) + 1
            if start_row == 1:

                set_with_dataframe(
                    worksheet,
                    df,
                    include_index=False,
                    include_column_header=True
                )

            else:
                set_with_dataframe(
                    worksheet,
                    df,
                    row=start_row,
                    include_index=False,
                    include_column_header=False
                )
        else:
            raise ValueError(
                f"Mode unrecognized: {mode}"
            )
        print(
            f"[GSpreadWriter] "
            f"{len(df)} rows written "
            f"to '{sheet_name}' "
            f"(mode={mode})"
        )
class GSpreadReader:

    def __init__(
        self,
        credentials_path: str,
        spreadsheet_id: str
    ):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes
        )

        self.client = gspread.authorize(creds)

        self.spreadsheet = self.client.open_by_key(
            spreadsheet_id
        )

    def read(self, sheet_name):

        try:

            worksheet = self.spreadsheet.worksheet(
                sheet_name
            )

            records = worksheet.get_all_records()

            if not records:

                return pd.DataFrame(
                    columns=[
                        "client_id",
                        "platform",
                        "year",
                        "month",
                        "metric",
                        "value"
                    ]
                )

            return pd.DataFrame(records)

        except gspread.exceptions.WorksheetNotFound:

            return pd.DataFrame(
                columns=[
                    "client_id",
                    "platform",
                    "year",
                    "month",
                    "metric",
                    "value"
                ]
            )