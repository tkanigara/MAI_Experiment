from langchain_core.tools import tool
import pandas as pd
from pathlib import Path

@tool
def get_data():
    """
    Load all client data from Excel
    """

    file_path = Path(
        "data/Dummy_Social_Media_Scraping_Data.xlsx"
    )

    excel_file = pd.ExcelFile(file_path)

    clients = {}

    for sheet_name in excel_file.sheet_names:

        df = pd.read_excel(
            excel_file,
            sheet_name=sheet_name
        )

        clients[sheet_name] = df.to_dict(
            orient="records"
        )

    return clients