from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import os
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env.example")
DATA_FOLDER = BASE_DIR / os.getenv("RAW_DATA")

class ReadCsv:
    def __init__(self, folder_path, platform, data_kind, client_name):
        self.folder_path = Path(folder_path)
        self.platform = platform
        self.data_kind = data_kind
        self.client_name = client_name
    
    def _find_files(self) ->list[Path]:
        print(f"Current folder: {self.folder_path}" )
        print(f"Exists: {self.folder_path.exists()}")
        print(f"Absolute: {self.folder_path.resolve()}")
        return sorted(self.folder_path.glob("*.csv"))
    
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

