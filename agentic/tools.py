from langchain_core.tools import tool
import os
import math
import pandas as pd
from typing import Dict, List, Any

# =========================================
# Path Configuration
# =========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FOLDER = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "..",
        "data",
        "processed"
    )
)

# =========================================
# Helper Functions
# =========================================

def clean_nan(obj):
    """
    Recursively convert NaN values into None
    so outputs become valid JSON for LLM tools.
    """

    if isinstance(obj, dict):

        return {
            key: clean_nan(value)
            for key, value in obj.items()
        }

    elif isinstance(obj, list):

        return [
            clean_nan(item)
            for item in obj
        ]

    elif isinstance(obj, float) and math.isnan(obj):

        return None

    return obj


def load_csv_dataframe(filename: str) -> pd.DataFrame:
    """
    Load CSV file into pandas DataFrame.
    """

    file_path = os.path.join(DATA_FOLDER, filename)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{filename} not found")

    try:

        df = pd.read_csv(file_path)

        # Convert NaN -> None
        df = df.where(pd.notnull(df), None)

        return df

    except Exception as e:
        raise Exception(f"Error loading CSV: {str(e)}")


# =========================================
# TOOLS
# =========================================

@tool
def list_csv_files() -> List[str]:
    """
    List all available CSV files in data folder.
    """

    if not os.path.exists(DATA_FOLDER):
        return []

    files = [
        file
        for file in os.listdir(DATA_FOLDER)
        if file.endswith(".csv")
    ]

    return clean_nan(files)


@tool
def build_kpi_report(filename: str) -> Dict[str, Any]:
    """
    Generate KPI report from CSV dataset.
    """

    try:

        df = load_csv_dataframe(filename)

        report = {
            "dataset_overview": get_dataset_overview(df),
            "kpi_summary": generate_kpi_summary(df),
            "sample_data": get_sample_data(df)
        }

        return clean_nan(report)

    except Exception as e:

        return {
            "error": str(e)
        }


@tool
def compare_target_vs_actual(
    filename: str,
    actual_column: str,
    target_column: str
) -> Dict[str, Any]:
    """
    Compare actual value against target value.
    """

    try:

        df = load_csv_dataframe(filename)

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

        status = (
            "Target Achieved"
            if achievement >= 100
            else "Below Target"
        )

        result = {
            "actual_total": float(actual_total),
            "target_total": float(target_total),
            "achievement_percent": round(float(achievement), 2),
            "status": status
        }

        return clean_nan(result)

    except Exception as e:

        return {
            "error": str(e)
        }


@tool
def get_top_performers(
    filename: str,
    category_column: str,
    value_column: str,
    top_n: int = 5
) -> Dict[str, float]:
    """
    Get top performers based on grouped aggregation.
    """

    try:

        df = load_csv_dataframe(filename)

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

        result = {
            str(key): float(value)
            for key, value in grouped.items()
        }

        return clean_nan(result)

    except Exception as e:

        return {
            "error": str(e)
        }


# =========================================
# Internal Analytics Functions
# =========================================

def get_dataset_overview(
    df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Generate dataset metadata overview.
    """

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

    return clean_nan(overview)


def generate_kpi_summary(
    df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Generate summary statistics for numeric columns.
    """

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

    return clean_nan(summary)


def get_sample_data(
    df: pd.DataFrame,
    rows: int = 5
) -> List[Dict[str, Any]]:
    """
    Get sample rows from dataset.
    """

    sample = df.head(rows).to_dict(orient="records")

    return clean_nan(sample)


# =========================================
# Tools Registry
# =========================================

TOOLS = [
    list_csv_files,
    build_kpi_report,
    compare_target_vs_actual,
    get_top_performers
]