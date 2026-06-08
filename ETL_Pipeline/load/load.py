import json
from pathlib import Path
from datetime import datetime, timezone

from ..transform.transform_csv import transform_all_clients


BASE_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "format_data"
)

BASE_OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)


def df_to_records(df):
    """
    Convert DataFrame ke JSON serializable.
    """

    records = []

    for row in df.to_dict(orient="records"):

        clean = {}

        for key, value in row.items():

            if isinstance(value, list):
                clean[key] = value

            elif value != value:  # NaN
                clean[key] = None

            else:
                clean[key] = value

        records.append(clean)

    return records


def generate_summary(platforms):

    total_posts = 0
    total_reach = 0
    total_views = 0
    total_interactions = 0

    for subfolders in platforms.values():

        for df in subfolders.values():

            total_posts += len(df)

            if "reach" in df.columns:
                total_reach += df["reach"].fillna(0).sum()

            if "views" in df.columns:
                total_views += df["views"].fillna(0).sum()

            if "total_interactions" in df.columns:
                total_interactions += (
                    df["total_interactions"]
                    .fillna(0)
                    .sum()
                )

    return {
        "total_posts": int(total_posts),
        "total_reach": int(total_reach),
        "total_views": int(total_views),
        "total_interactions": int(total_interactions)
    }


def get_scraped_at(platforms):

    timestamps = []

    for subfolders in platforms.values():

        for df in subfolders.values():

            if "timestamp" not in df.columns:
                continue

            ts = df["timestamp"].dropna()

            if not ts.empty:
                timestamps.extend(ts.tolist())

    if timestamps:
        return max(timestamps)

    return datetime.now(
        timezone.utc
    ).isoformat()


def create_snapshot_id(scraped_at):

    try:

        return (
            datetime
            .fromisoformat(
                scraped_at.replace(
                    "Z",
                    "+00:00"
                )
            )
            .strftime("%Y%m%d")
        )

    except Exception:

        return datetime.now().strftime(
            "%Y%m%d"
        )


def save_metadata(
    snapshot_folder,
    client_name,
    snapshot_id,
    scraped_at,
    summary,
    platforms
):

    metadata = {
        "client": client_name,
        "snapshot_id": snapshot_id,
        "scraped_at": scraped_at,
        "etl_created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "summary": summary,
        "platforms": list(
            platforms.keys()
        )
    }

    with open(
        snapshot_folder / "metadata.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            ensure_ascii=False,
            indent=4
        )


def save_platform_data(
    snapshot_folder,
    platforms
):

    for platform, subfolders in platforms.items():

        platform_folder = (
            snapshot_folder
            / platform
        )

        platform_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        for subfolder, df in subfolders.items():

            output_file = (
                platform_folder
                / f"{subfolder}.json"
            )

            with open(
                output_file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    df_to_records(df),
                    f,
                    ensure_ascii=False,
                    indent=4
                )

            print(
                f"Saved -> {output_file}"
            )


def load_to_json():

    transformed_data = (
        transform_all_clients()
    )

    for client_name, platforms in (
        transformed_data.items()
    ):

        scraped_at = (
            get_scraped_at(
                platforms
            )
        )

        snapshot_id = (
            create_snapshot_id(
                scraped_at
            )
        )

        summary = (
            generate_summary(
                platforms
            )
        )

        snapshot_folder = (
            BASE_OUTPUT
            / client_name
            / snapshot_id
        )

        snapshot_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        save_metadata(
            snapshot_folder,
            client_name,
            snapshot_id,
            scraped_at,
            summary,
            platforms
        )

        save_platform_data(
            snapshot_folder,
            platforms
        )

        print(
            f"\nClient : {client_name}"
        )

        print(
            f"Snapshot : {snapshot_id}"
        )

        print(
            f"Folder : {snapshot_folder}\n"
        )


if __name__ == "__main__":
    load_to_json()