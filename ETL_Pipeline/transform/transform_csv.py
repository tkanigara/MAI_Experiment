import pandas as pd
from pathlib import Path


DATA_FOLDER = Path(__file__).resolve().parents[2] / "data"


def transform_all_clients():
    transformed_data = {}

    excel_files = DATA_FOLDER.glob("*.xlsx")

    for file in excel_files:
        client_name = file.stem

        print(f"Processing {client_name}")

        xls = pd.ExcelFile(file)

        all_sheets = []

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet_name)
            df["platform"] = sheet_name
            df.columns = (
                df.columns
                .str.strip()
                .str.lower()
                .str.replace(" ", "_")
            )

            all_sheets.append(df)

        merged_df = pd.concat(all_sheets, ignore_index=True)

        transformed_data[client_name] = merged_df

    return transformed_data


if __name__ == "__main__":
    result = transform_all_clients()

    for client, df in result.items():
        print(f"\n{client}")
        print(df.head())