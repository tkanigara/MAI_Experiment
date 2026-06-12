from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import os

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
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
        df["source_folder"] = self.data_kind
        df["source_file"] = file.name
        return df
    
    def read_all(self) -> list[pd.DataFrame]:
        files = self._find_files()
        if not files:
            print(f"Empty csv files for {self.data_kind}")
            return []
        return [self._read_one(f) for f in files]
    


for client_dir in DATA_FOLDER.iterdir():
    if not client_dir.is_dir():
        continue

    client_name = client_dir.name
    print(f"Processing {client_name} \n")

    for platform_dir in client_dir.iterdir():
        if not platform_dir.is_dir():
            continue

        print(f"Platform finding: {platform_dir.name}")
        platform = platform_dir.name

        for kind_dir in platform_dir.iterdir():
            if not kind_dir.is_dir():
                continue
            data_kind = kind_dir.name

            reader = ReadCsv(
                folder_path=kind_dir,
                platform=platform,
                data_kind=data_kind,
                client_name=client_name
            )

            dfs = reader.read_all()
            print(f"Loaded {len(dfs)} files")