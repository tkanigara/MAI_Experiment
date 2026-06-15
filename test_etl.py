from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import os

from ETL_Pipeline.transform.read_file import ReadCsv
from ETL_Pipeline.transform.kpi import KPIProcessor, GSpreadWritter


BASE_DIR = Path(__file__).resolve().parents[0]

load_dotenv(BASE_DIR / ".env.example")

DATA_FOLDER = BASE_DIR / os.getenv("RAW_DATA")


writer = GSpreadWritter(
    credentials_path=str(
        BASE_DIR
        / "config"
        / os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    ),
    spreadsheet_id=os.getenv("INTERMEDIATE_SPREADSHEET_ID")
)
first_write = True


for client_dir in DATA_FOLDER.iterdir():

    if not client_dir.is_dir():
        continue

    client_name = client_dir.name

    print(f"\nProcessing Client: {client_name}")

    for platform_dir in client_dir.iterdir():

        if not platform_dir.is_dir():
            continue

        platform = platform_dir.name

        print(f"Platform: {platform}")

        account_folder = platform_dir / "account"
        media_folder = platform_dir / "media"

        account_reader = ReadCsv(
            folder_path=account_folder,
            platform=platform,
            data_kind="account",
            client_name=client_name
        )

        media_reader = ReadCsv(
            folder_path=media_folder,
            platform=platform,
            data_kind="media",
            client_name=client_name
        )

        account_files = account_reader.read_all()
        media_files = media_reader.read_all()

        account_df = (
            pd.concat(account_files, ignore_index=True)
            if account_files
            else pd.DataFrame()
        )

        media_df = (
            pd.concat(media_files, ignore_index=True)
            if media_files
            else pd.DataFrame()
        )

        if account_df.empty and media_df.empty:

            print(
                f"Skip {client_name}/{platform} "
                f"(no data)"
            )

            continue

        processor = KPIProcessor(
            account_df=account_df,
            media_df=media_df,
            gspread_writer=writer
        )

        result_df = processor.generate()

        if result_df.empty:

            print(
                f"Skip {client_name}/{platform} "
                f"(no KPI)"
            )

            continue

        print(result_df)

        write_mode = (
            "replace"
            if first_write
            else "append"
        )

        writer.write(
            result_df,
            sheet_name="kpi",
            mode=write_mode
        )

        first_write = False

print("\nETL Finished")