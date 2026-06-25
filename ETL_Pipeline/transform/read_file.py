from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import os
from datetime import datetime
import re

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
DATA_FOLDER = BASE_DIR / os.getenv("DATA_FOLDER", "data")

class ReadCsv:
    def __init__(
        self,
        folder_path,
        platform,
        data_kind,
        client_name,
        latest_per_period=True,
        latest_only=False,
    ):
        self.folder_path = Path(folder_path)
        self.platform = platform
        self.data_kind = data_kind
        self.client_name = client_name
        self.latest_per_period = latest_per_period
        self.latest_only = latest_only
    
    def _find_files(self) ->list[Path]:
        print(f"Current folder: {self.folder_path}" )
        print(f"Exists: {self.folder_path.exists()}")
        print(f"Absolute: {self.folder_path.resolve()}")
        if not self.folder_path.exists():
            return []

        pattern = self._file_pattern()
        files = sorted(self.folder_path.glob(pattern))
        if self.latest_per_period:
            files = self._latest_files_by_period(files)
        if self.latest_only:
            files = self._latest_files(files)
        return files

    def _file_pattern(self):
        if self.data_kind in ("account", "media"):
            return f"{self.platform}_{self.data_kind}_raw*.csv"
        return "*.csv"

    def _report_period_from_name(self, file: Path):
        match = re.search(r"_raw_(\d{4}-\d{2})_", file.name)
        if match:
            return match.group(1)
        scrapped_at = self._extract_scrapped_at(file)
        if scrapped_at:
            return scrapped_at.strftime("%Y-%m")
        return file.stem

    def _latest_files_by_period(self, files):
        latest = {}
        for file in files:
            period = self._report_period_from_name(file)
            scrapped_at = self._extract_scrapped_at(file) or datetime.fromtimestamp(
                file.stat().st_mtime
            )
            current = latest.get(period)
            if not current or scrapped_at > current[0]:
                latest[period] = (scrapped_at, file)
        return [
            item[1]
            for item in sorted(latest.values(), key=lambda value: value[0])
        ]

    def _latest_files(self, files):
        if not files:
            return []
        return [
            max(
                files,
                key=lambda file: self._extract_scrapped_at(file)
                or datetime.fromtimestamp(file.stat().st_mtime),
            )
        ]
    
    def _read_one(self, file: Path) -> pd.DataFrame:
        print(f"Reading: {file.name}")
        df = pd.read_csv(file)
        df = self._attach_metadata(df, file)
        return df
    
    def _attach_metadata(self, df: pd.DataFrame, file: Path) -> pd.DataFrame:
        df["client"] = self.client_name
        df["platform"] = self.platform
        df["data_kind"] = self.data_kind
        df["source_file"] = file.name
        df["scrapped_at"] = self._extract_scrapped_at(file)
        return df
    
    def read_all(self) -> list[pd.DataFrame]:
        files = self._find_files()
        if not files:
            print(f"Empty csv files for {self.data_kind}")
            return []
        return [self._read_one(f) for f in files]
    
    def _extract_scrapped_at(self, file: Path):
        try:
            parts = file.stem.split("_")

            date_str = parts[-2]
            time_str = parts[-1]

            return datetime.strptime(
                f"{date_str}_{time_str}",
                "%Y%m%d_%H%M%S"
            )

        except Exception as e:
            print(f"Cannot parse date from {file.name}: {e}")
            return None

