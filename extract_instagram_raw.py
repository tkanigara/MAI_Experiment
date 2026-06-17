import argparse
import json
import os
from datetime import datetime, timezone

from ETL_Pipeline.extract.instagram import extract_instagram_raw
from ETL_Pipeline.extract.meta_instagram import load_dotenv


def run_id_for(client_id):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_client = "".join(char if char.isalnum() or char in "-_" else "_" for char in client_id)
    return f"{safe_client}_{stamp}"


def parse_args():
    parser = argparse.ArgumentParser(description="Extract Instagram raw account/media CSV only.")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--frequency", default="weekly", choices=["daily", "weekly", "monthly"])
    parser.add_argument("--limit", type=int, default=int(os.getenv("META_EXPORT_LIMIT", "25")))
    parser.add_argument("--month", help="Bulan laporan, contoh 2026-05, june, atau mei 2026.")
    parser.add_argument("--since", help="Tanggal awal atau Unix timestamp untuk media insight Meta.")
    parser.add_argument("--until", help="Tanggal akhir atau Unix timestamp untuk media insight Meta.")
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--ig-business-id", default=None)
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    run_id = run_id_for(args.client_id)
    result = extract_instagram_raw(
        client_id=args.client_id,
        run_id=run_id,
        frequency=args.frequency,
        limit=args.limit,
        month=args.month,
        since=args.since,
        until=args.until,
        output_root=args.output_dir,
        ig_business_id=args.ig_business_id,
    )
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "client_id": result["client_id"],
                "platform": result["platform"],
                "report_month": result.get("report_month", ""),
                "report_since": result.get("report_since", ""),
                "report_until": result.get("report_until", ""),
                "account_csv": str(result["account_csv"]),
                "media_csv": str(result["media_csv"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
