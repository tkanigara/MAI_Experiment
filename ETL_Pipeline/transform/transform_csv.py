import pandas as pd
import json
from pathlib import Path

DATA_FOLDER = Path(__file__).resolve().parents[2] / "data"

PLATFORM_CONFIG = {
    "instagram": {
        "subfolders": ["account", "media"],
        "schema": {
            # --- Identitas ---
            "post_id":              "id",
            "username":             "username",
            "platform":             "platform",
            "timestamp":            "timestamp",
            "permalink":            "permalink",

            # --- Tipe konten ---
            "content_type":         "media_type",
            "content_format":       "media_product_type",

            # --- Teks ---
            "caption":              "caption",

            # --- KPI: Reach & Visibility ---
            "reach":                "insight_reach",
            "views":                "insight_views",

            # --- KPI: Engagement ---
            "likes":                "insight_likes",
            "comments":             "insight_comments",
            "shares":               "insight_shares",
            "saves":                "insight_saved",
            "total_interactions":   "insight_total_interactions",

            # --- KPI: Account ---
            "followers":            "followers_count",
            "following":            "follows_count",
            "total_posts":          "media_count",

            # --- Error tracking ---
            "metric_errors":        "metric_errors",
        }
    },
    # "tiktok": {
    #     "subfolders": ["account", "video"],
    #     "schema": {
    #         "post_id":            "video_id",
    #         "username":           "author_unique_id",
    #         "platform":           "platform",
    #         "timestamp":          "create_time",   # <-- sesuaikan nama kolom scraping
    #         ...
    #     }
    # },
}

STANDARD_COLUMNS = [
    "client", "platform", "source_folder", "source_file",
    "username", "post_id",
    "timestamp",
    "date",         # ← TAMBAHAN: tanggal saja (YYYY-MM-DD), derived dari timestamp
    "permalink",
    "content_type", "content_format", "caption",
    "reach", "views",
    "likes", "comments", "shares", "saves", "total_interactions",
    "followers", "following", "total_posts",
    "metric_errors",
]


def map_to_standard_schema(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Rename & select kolom sesuai schema standar. Kolom tidak ada → NaN."""
    mapped = {}
    for std_col, raw_col in schema.items():
        if raw_col and raw_col in df.columns:
            mapped[std_col] = df[raw_col]
        else:
            mapped[std_col] = pd.NA
    return pd.DataFrame(mapped)


def extract_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive kolom 'date' (YYYY-MM-DD) dari kolom 'timestamp'.
    Handle format ISO 8601 dengan timezone offset: 2026-05-10T08:13:43+0000
    """
    if "timestamp" in df.columns and df["timestamp"].notna().any():
        df["date"] = (
            pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            .dt.normalize()
            .dt.strftime("%Y-%m-%d")
        )
    else:
        df["date"] = pd.NA
    return df


def parse_metric_errors(df: pd.DataFrame) -> pd.DataFrame:
    """Ekstrak error keys dari kolom metric_errors (JSON string)."""
    if "metric_errors" not in df.columns:
        return df

    def extract_error_keys(val):
        if pd.isna(val) or val == "":
            return None
        try:
            errors = json.loads(val)
            return list(errors.keys())
        except (json.JSONDecodeError, TypeError):
            return None

    df["metric_errors"] = df["metric_errors"].apply(extract_error_keys)
    return df


def read_csv_from_folder(
    folder_path: Path,
    subfolder: str,
    platform: str,
    schema: dict,
    client_name: str,
) -> list[pd.DataFrame]:
    """Baca semua CSV dari satu subfolder, map ke schema standar."""
    subfolder_path = folder_path / subfolder

    if not subfolder_path.exists():
        print(f"    Skipping '{subfolder}': folder tidak ditemukan")
        return []

    csv_files = list(subfolder_path.glob("*.csv"))
    if not csv_files:
        print(f"    Tidak ada file CSV di '{subfolder}'")
        return []

    dfs = []
    for file in csv_files:
        print(f"    Reading: {file.name}")

        raw_df = pd.read_csv(file)
        raw_df.columns = (
            raw_df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        std_df = map_to_standard_schema(raw_df, schema)
        std_df = extract_date(std_df)
        std_df = parse_metric_errors(std_df)

        std_df["client"]        = client_name
        std_df["source_folder"] = subfolder
        std_df["source_file"]   = file.name
        std_df["platform"]      = platform

        dfs.append(std_df)

    return dfs


def enforce_standard_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Pastikan semua kolom standar ada dan urutannya konsisten."""
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[STANDARD_COLUMNS]


def transform_client(client_folder: Path) -> dict[str, dict[str, pd.DataFrame]]:
    """
    Transform semua platform untuk satu client.
    Return: { platform: { subfolder: df } }
    """
    client_name = client_folder.name
    result = {}

    for platform, config in PLATFORM_CONFIG.items():
        platform_path = client_folder / "raw_data" / platform

        if not platform_path.exists():
            print(f"  [{platform}] Folder tidak ditemukan, skipping")
            continue

        print(f"  [{platform}] Processing...")
        platform_data = {}

        for subfolder in config["subfolders"]:
            dfs = read_csv_from_folder(
                platform_path, subfolder,
                platform, config["schema"], client_name,
            )
            if dfs:
                merged = pd.concat(dfs, ignore_index=True)
                merged = enforce_standard_columns(merged)
                platform_data[subfolder] = merged
                print(f"  [{platform}/{subfolder}] {len(merged)} rows loaded")
            else:
                print(f"  [{platform}/{subfolder}] Tidak ada data")

        if platform_data:
            result[platform] = platform_data

    return result


def transform_all_clients() -> dict[str, dict[str, dict[str, pd.DataFrame]]]:
    """
    Return: { client_name: { platform: { subfolder: df } } }
    """
    transformed_data = {}

    client_folders = [f for f in DATA_FOLDER.iterdir() if f.is_dir()]
    if not client_folders:
        print(f"Tidak ada folder client di {DATA_FOLDER}")
        return transformed_data

    for client_folder in client_folders:
        client_name = client_folder.name
        print(f"\n{'='*50}")
        print(f"Client: {client_name}")

        client_data = transform_client(client_folder)
        if client_data:
            transformed_data[client_name] = client_data

    return transformed_data


if __name__ == "__main__":
    result = transform_all_clients()

    for client, platforms in result.items():
        print(f"\n{'='*50} Client: {client}")
        for platform, subfolders in platforms.items():
            for subfolder, df in subfolders.items():
                print(f"  [{platform}/{subfolder}] {len(df)} rows")
                print(df[["username", "date", "content_type", "reach", "likes"]].head(2))