import json
from pathlib import Path

from ..transform.transform_csv import transform_all_clients


OUTPUT_FOLDER = Path(__file__).resolve().parents[2] / "data" / "processed"

OUTPUT_FOLDER.mkdir(exist_ok=True)


def load_to_json():

    transformed_data = transform_all_clients()

    for client_name, df in transformed_data.items():

        output_file = OUTPUT_FOLDER / f"{client_name}.json"

        records = df.fillna("").to_dict(orient="records")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                records,
                f,
                ensure_ascii=False,
                indent=4
            )

        print(f"Saved -> {output_file}")


if __name__ == "__main__":
    load_to_json()