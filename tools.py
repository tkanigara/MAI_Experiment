import os
import pandas as pd

DATA_FOLDER = "data/processed"

def list_csv_files():
    if not os.path.exists(DATA_FOLDER):
        return []

    files = [
        file for file in os.listdir(DATA_FOLDER)
        if file.endswith(".csv")
    ]

    return files


def load_csv_data(filename):
    file_path = os.path.join(DATA_FOLDER, filename)

    if not os.path.exists(file_path):
        return None

    try:
        df = pd.read_csv(file_path)
        return df

    except Exception as e:
        return f"Error loading CSV: {str(e)}"


def get_dataset_overview(df):
    overview = {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "columns": list(df.columns),
        "data_types": {
            col: str(dtype)
            for col, dtype in df.dtypes.items()
        },
        "missing_values": {
            col: int(val)
            for col, val in df.isnull().sum().items()
        }
    }

    return overview


def generate_kpi_summary(df):
    numeric_df = df.select_dtypes(include=["number"])

    if numeric_df.empty:
        return {
            "message": "No numeric columns found"
        }

    summary = {}

    for column in numeric_df.columns:

        summary[column] = {
            "total": float(numeric_df[column].sum()),
            "average": float(numeric_df[column].mean()),
            "minimum": float(numeric_df[column].min()),
            "maximum": float(numeric_df[column].max())
        }

    return summary


def compare_target_vs_actual(
    df,
    actual_column,
    target_column
):

    if actual_column not in df.columns:
        return {
            "error": f"{actual_column} not found"
        }

    if target_column not in df.columns:
        return {
            "error": f"{target_column} not found"
        }

    actual_total = df[actual_column].sum()
    target_total = df[target_column].sum()

    achievement = (
        (actual_total / target_total) * 100
        if target_total != 0 else 0
    )

    status = "Below Target"

    if achievement >= 100:
        status = "Target Achieved"

    return {
        "actual_total": float(actual_total),
        "target_total": float(target_total),
        "achievement_percent": round(float(achievement), 2),
        "status": status
    }


def get_top_performers(
    df,
    category_column,
    value_column,
    top_n=5
):

    if category_column not in df.columns:
        return {
            "error": f"{category_column} not found"
        }

    if value_column not in df.columns:
        return {
            "error": f"{value_column} not found"
        }

    grouped = (
        df.groupby(category_column)[value_column]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
    )

    return grouped.to_dict()


def get_sample_data(df, rows=5):
    return df.head(rows).to_dict(orient="records")



def build_kpi_report_data(filename):
    df = load_csv_data(filename)

    if df is None:
        return {
            "error": "File not found"
        }

    if isinstance(df, str):
        return {
            "error": df
        }

    report = {
        "dataset_overview": get_dataset_overview(df),
        "kpi_summary": generate_kpi_summary(df),
        "sample_data": get_sample_data(df)
    }

    return report


TOOLS = {
    "LIST_FILES": list_csv_files,
    "LOAD_CSV": load_csv_data,
    "BUILD_KPI_REPORT": build_kpi_report_data,
    "KPI_SUMMARY": generate_kpi_summary,
    "COMPARE_TARGET": compare_target_vs_actual,
    "TOP_PERFORMERS": get_top_performers
}
