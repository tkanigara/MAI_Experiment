import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_insight_pipeline import fallback_insights, generate_ai_insight
from analytics_pipeline import calculate_instagram_kpi, dumps_compact, latest_csv
from meta_export import (
    DEFAULT_API_VERSION,
    MetaApiError,
    MetaClient,
    env_required,
    export_instagram,
    export_instagram_account,
    load_dotenv,
    write_csv,
)
from push_to_sheets import append_report_run, push_intermediate_run


DEFAULT_OUTPUT_DIR = Path("data/processed")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_id_for(client_id):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_client = "".join(char if char.isalnum() or char in "-_" else "_" for char in client_id)
    return f"{safe_client}_{stamp}"


def parse_args():
    parser = argparse.ArgumentParser(description="Scheduler-ready MAI Instagram pipeline.")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--frequency", required=True, choices=["daily", "weekly", "monthly"])
    parser.add_argument("--limit", type=int, default=int(os.getenv("META_EXPORT_LIMIT", "5")))
    parser.add_argument("--since", help="Tanggal awal atau Unix timestamp untuk insight Meta.")
    parser.add_argument("--until", help="Tanggal akhir atau Unix timestamp untuk insight Meta.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true", help="Tidak fetch Meta, tidak tulis Sheets, tidak generate Slides.")
    parser.add_argument("--generate-slides", action="store_true", help="Generate Google Slides setelah Sheets berhasil.")
    parser.add_argument("--no-slides", action="store_true", help="Matikan generate Slides eksplisit.")
    return parser.parse_args()


def fetch_instagram_to_csv(args, run_id):
    token = env_required("META_ACCESS_TOKEN")
    ig_business_id = env_required("IG_BUSINESS_ID")
    api_version = os.environ.get("META_API_VERSION", DEFAULT_API_VERSION).strip()
    output_dir = Path(args.output_dir)
    client = MetaClient(token, api_version)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    account_rows = export_instagram_account(client, ig_business_id, args.since, args.until)
    account_csv = output_dir / f"instagram_account_{stamp}_{run_id}.csv"
    write_csv(account_csv, account_rows)

    media_rows = export_instagram(client, ig_business_id, args.limit, args.since, args.until)
    media_csv = output_dir / f"instagram_media_{stamp}_{run_id}.csv"
    write_csv(media_csv, media_rows)
    return media_csv, account_csv


def dry_run_sources(output_dir):
    media_csv = latest_csv(output_dir, "instagram_media_*.csv")
    account_csv = latest_csv(output_dir, "instagram_account_*.csv")
    return media_csv, account_csv


def empty_kpi(media_csv=None, account_csv=None):
    if media_csv:
        return calculate_instagram_kpi(media_csv, account_csv)
    return calculate_instagram_kpi("__dry_run_missing_instagram_media__.csv", account_csv)


def maybe_generate_slides(args, media_csv, account_csv, ai_insights):
    if args.no_slides or not args.generate_slides:
        return ""

    from dotenv import load_dotenv as python_dotenv
    from generate_slides_example import generate_slides_report

    python_dotenv()
    template = os.getenv("SLIDES_TEMPLATE_ID") or os.getenv("GOOGLE_SLIDES_TEMPLATE_ID")
    credentials = (
        os.getenv("GOOGLE_SLIDES_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    )
    token = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    result = generate_slides_report(
        template=template if template else "https://docs.google.com/presentation/d/1ZeYnxJOVIjjEbHqa6BJBh30JE3m2SVQuyEcOu4WaiMY/edit?usp=sharing",
        csv=media_csv,
        account_csv=account_csv,
        client_name=args.client_id,
        report_period=f"{args.frequency} {datetime.now().strftime('%B %Y')}",
        credentials=credentials,
        token=token,
        dry_run=False,
        use_ai_insights=False,
        ai_insights=ai_insights,
    )
    return result.get("presentation_url", "")


def print_dry_run_summary(payload):
    summary = {
        "run_id": payload["run_id"],
        "client_id": payload["client_id"],
        "frequency": payload["frequency"],
        "media_csv": str(payload.get("media_csv") or ""),
        "account_csv": str(payload.get("account_csv") or ""),
        "would_write_sheets": False,
        "would_generate_slides": False,
        "kpi": {
            "total_posts": payload["kpi_summary"].get("total_posts", 0),
            "total_reach": payload["kpi_summary"].get("total_reach", 0),
            "total_views": payload["kpi_summary"].get("total_views", 0),
            "total_interactions": payload["kpi_summary"].get("total_interactions", 0),
            "avg_engagement_rate": payload["kpi_summary"].get("avg_engagement_rate", 0),
            "best_content_type": payload["kpi_summary"].get("best_content_type", ""),
        },
        "ai_warning": payload["ai_insights"].get("warning", ""),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    load_dotenv()
    args = parse_args()
    run_id = run_id_for(args.client_id)
    started_at = utc_now()
    media_csv = None
    account_csv = None
    slides_url = ""
    warning = ""

    if args.generate_slides and args.no_slides:
        raise SystemExit("Use either --generate-slides or --no-slides, not both.")

    try:
        if args.dry_run:
            media_csv, account_csv = dry_run_sources(args.output_dir)
            kpi_summary = empty_kpi(media_csv, account_csv)
        else:
            media_csv, account_csv = fetch_instagram_to_csv(args, run_id)
            kpi_summary = calculate_instagram_kpi(media_csv, account_csv)

        if args.dry_run:
            ai_insights = fallback_insights(kpi_summary, "Dry-run mode; Gemini was not called.")
        else:
            ai_insights = generate_ai_insight(kpi_summary, args.client_id, args.frequency)
        warning = ai_insights.get("warning", "")

        payload = {
            "run_id": run_id,
            "client_id": args.client_id,
            "frequency": args.frequency,
            "media_csv": media_csv,
            "account_csv": account_csv,
            "kpi_summary": kpi_summary,
            "ai_insights": ai_insights,
        }

        if args.dry_run:
            print_dry_run_summary(payload)
            return

        service = push_intermediate_run(
            run_id,
            args.client_id,
            args.frequency,
            media_csv,
            account_csv,
            kpi_summary,
            ai_insights,
        )

        status = "success"
        try:
            slides_url = maybe_generate_slides(args, media_csv, account_csv, ai_insights)
        except Exception as exc:
            status = "partial_success"
            warning = (warning + " " if warning else "") + f"Slides failed: {exc}"

        append_report_run(
            run_id,
            args.client_id,
            args.frequency,
            started_at,
            status,
            media_csv,
            account_csv,
            slides_url,
            warning,
            service=service,
        )

        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": status,
                    "media_csv": str(media_csv),
                    "account_csv": str(account_csv),
                    "slides_url": slides_url,
                    "warning": warning,
                    "kpi_summary": json.loads(dumps_compact(kpi_summary)),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    except MetaApiError as exc:
        error = f"Meta API error: {exc}"
        print(error, file=sys.stderr)
        try:
            append_report_run(
                run_id,
                args.client_id,
                args.frequency,
                started_at,
                "failed",
                media_csv,
                account_csv,
                "",
                warning,
                error,
            )
        except Exception:
            pass
        raise SystemExit(1) from exc
    except Exception as exc:
        error = str(exc)
        print(f"Pipeline failed: {error}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
