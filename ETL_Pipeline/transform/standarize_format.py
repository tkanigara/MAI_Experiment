from __future__ import annotations
from enum import Enum
import pandas as pd

class UnknownCols(Enum):
    DROP = "drop"
    KEEP = "keep"
    EXTRAS = "extras"

class MissingCols(Enum):
    FILL_NA = "fill_na"
    SKIP = "skip"

SCHEMA_ACCOUNT_CSV: dict[str, dict[str, str]] = {
    "instagram:":{},
    "tiktok": {},
    "youtube": {},
    "facebook": {}
}

SCHEMA_MEDIA_CSV: dict[str, dict[str, str]] = {
    "instagram:":{},
    "tiktok": {},
    "youtube": {},
    "facebook": {}
}

class Standarize:
    def __init__(self, platform: str, unknown_pol: UnknownCols = UnknownCols.KEEP, missing_col: MissingCols = MissingCols.FILL_NA):
        if (platform not in SCHEMA_ACCOUNT_CSV and platform not in SCHEMA_MEDIA_CSV):
            raise ValueError(f"Platform {platform} not in schema")
        self.platform = platform
        self.unknown_pol = unknown_pol
        self.missing_col = missing_col
        self.schema_media = SCHEMA_MEDIA_CSV[platform]
        self.schema_account = SCHEMA_ACCOUNT_CSV[platform]
        self.schema = {**self.schema_account, **self.schema_media}
        self._raw_to_std: dict [str, str] = {v: k for k, v in self.schema.items()}
    
    def rename_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        rename_map = {
            raw: std
            for raw, std in self._raw_to_std.items()
            if raw in df.columns
        }

        return df.rename(columns=rename_map)
    
    def handle_unknown_col(self, df: pd.DataFrame) -> pd.DataFrame:
        std_cols = set (self.schema.keys())
        unknown = [c for c in df.columns if c not in std_cols]

        if not unknown:
            return df
        
        if self.unknown_pol == UnknownCols.DROP:
            df = df.drop(columns=unknown)

        elif self.unknown_pol == UnknownCols.EXTRAS:
            df["extra_columns"] = df[unknown].apply(
                lambda row: row.dropna().to_dict(), axis=1
            )
            df = df.drop(columns=unknown)
        
        return df
    
    def handle_missing_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        std_columns   = set(self.schema.keys())
        present       = set(df.columns)
        missing       = std_columns - present

        if not missing:
            return df

        if self.missing_col == MissingCols.FILL_NA:
            for col in missing:
                df[col] = pd.NA
        return df

    
    def standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.rename_cols(df)
        df = self.handle_missing_columns(df)
        df = self.handle_unknown_col(df)
        return df
    
