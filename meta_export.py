import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_API_VERSION = "v23.0"


class MetaApiError(Exception):
    """Error kecil supaya pesan error dari Meta API lebih mudah ditangkap."""

    pass


def load_dotenv(path=".env"):
    """Load file .env sederhana tanpa dependency tambahan.

    Format yang didukung:
    META_ACCESS_TOKEN=...
    IG_BUSINESS_ID=...

    Nilai dari terminal tetap diprioritaskan. Jadi kalau environment variable
    sudah diset manual, isi .env tidak akan menimpa.
    """
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class MetaClient:
    """Wrapper tipis untuk request ke Meta Graph API."""

    def __init__(self, token, api_version):
        self.token = token
        self.base_url = f"https://graph.facebook.com/{api_version}"

    def get(self, path, params=None):
        params = dict(params or {})
        params["access_token"] = self.token
        url = f"{self.base_url}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=40) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"error": {"message": body}}
            error = payload.get("error", {})
            message = error.get("message", body)
            raise MetaApiError(message) from exc
        except urllib.error.URLError as exc:
            raise MetaApiError(str(exc)) from exc

    def get_all_pages(self, path, params=None, limit_pages=20):
        """Ambil data yang punya pagination sampai habis atau limit page tercapai."""
        items = []
        payload = self.get(path, params=params)
        pages_seen = 0

        while payload and pages_seen < limit_pages:
            items.extend(payload.get("data", []))
            next_url = payload.get("paging", {}).get("next")
            if not next_url:
                break
            with urllib.request.urlopen(next_url, timeout=40) as response:
                payload = json.loads(response.read().decode("utf-8"))
            pages_seen += 1

        return items


def env_required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing environment variable: {name}")
    return value


def clean_text(value):
    """Rapikan text panjang supaya aman masuk satu cell CSV."""
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def metric_value(insights_payload, metric_name):
    """Ambil nilai metric terakhir dari response /insights."""
    for item in insights_payload.get("data", []):
        if item.get("name") != metric_name:
            continue
        values = item.get("values", [])
        if not values:
            return ""
        value = values[-1].get("value", "")
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value
    return ""


def fetch_metric_group(client, object_id, metrics, period=None, since=None, until=None):
    params = {"metric": ",".join(metrics)}
    if period:
        params["period"] = period
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    return client.get(f"{object_id}/insights", params=params)


def fetch_supported_metrics(client, object_id, candidates, period=None, since=None, until=None):
    """Coba ambil beberapa metric sekaligus, lalu fallback satu-satu kalau ditolak.

    Meta sering mengubah nama/availability metric berdasarkan API version,
    permission token, jenis media, dan tipe akun. Fallback ini bikin export tetap
    jalan walaupun sebagian metric tidak tersedia.
    """
    results = {}
    errors = {}

    try:
        payload = fetch_metric_group(client, object_id, candidates, period, since, until)
        for metric in candidates:
            results[metric] = metric_value(payload, metric)
        return results, errors
    except MetaApiError as exc:
        errors["group"] = str(exc)

    for metric in candidates:
        try:
            payload = fetch_metric_group(client, object_id, [metric], period, since, until)
            results[metric] = metric_value(payload, metric)
        except MetaApiError as exc:
            errors[metric] = str(exc)

    return results, errors


def write_csv(path, rows):
    """Tulis CSV dengan urutan kolom penting di depan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = [
        "platform",
        "object_level",
        "id",
        "created_time",
        "timestamp",
        "media_type",
        "media_product_type",
        "message",
        "caption",
        "permalink_url",
        "permalink",
    ]
    ordered = [key for key in preferred if key in fieldnames]
    ordered.extend(key for key in fieldnames if key not in ordered)

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=ordered)
        writer.writeheader()
        writer.writerows(rows)


def diagnose(client, fb_page_id=None, ig_business_id=None):
    """Cek token dan ID yang diberikan bisa akses data apa saja."""
    checks = []

    for label, path, params in [
        ("token_owner_me", "me", {"fields": "id,name"}),
        (
            "user_pages_if_user_token",
            "me/accounts",
            {
                "fields": (
                    "id,name,category,tasks,instagram_business_account"
                    "{id,username,name,profile_picture_url}"
                ),
                "limit": 25,
            },
        ),
    ]:
        try:
            checks.append({"check": label, "ok": True, "response": client.get(path, params)})
        except MetaApiError as exc:
            checks.append({"check": label, "ok": False, "error": str(exc)})

    if fb_page_id:
        try:
            checks.append(
                {
                    "check": "fb_page_id",
                    "ok": True,
                    "response": client.get(
                        fb_page_id,
                        {
                            "fields": (
                                "id,name,category,fan_count,followers_count,"
                                "instagram_business_account{id,username,name}"
                            )
                        },
                    ),
                }
            )
        except MetaApiError as exc:
            checks.append({"check": "fb_page_id", "ok": False, "error": str(exc)})

        for label, edge in [
            ("fb_page_posts_minimal", "posts"),
            ("fb_page_feed_minimal", "feed"),
        ]:
            try:
                checks.append(
                    {
                        "check": label,
                        "ok": True,
                        "response": client.get(
                            f"{fb_page_id}/{edge}",
                            {"fields": "id,message,created_time,permalink_url", "limit": 1},
                        ),
                    }
                )
            except MetaApiError as exc:
                checks.append({"check": label, "ok": False, "error": str(exc)})

    if ig_business_id:
        try:
            checks.append(
                {
                    "check": "ig_business_id",
                    "ok": True,
                    "response": client.get(
                        ig_business_id,
                        {
                            "fields": (
                                "id,username,name,biography,followers_count,"
                                "follows_count,media_count"
                            )
                        },
                    ),
                }
            )
        except MetaApiError as exc:
            checks.append({"check": "ig_business_id", "ok": False, "error": str(exc)})

    return checks


def export_instagram(client, ig_business_id, limit, since=None, until=None):
    print(f"Instagram: mengambil daftar media, maksimal {limit} item...", flush=True)
    media_fields = (
        "id,caption,media_type,media_product_type,media_url,permalink,"
        "thumbnail_url,timestamp,username,like_count,comments_count"
    )
    media = client.get_all_pages(
        f"{ig_business_id}/media",
        params={"fields": media_fields, "limit": min(limit, 100)},
    )[:limit]
    total = len(media)
    print(f"Instagram: ditemukan {total} media. Mulai ambil insight per media.", flush=True)

    insight_candidates = [
        "views",
        "reach",
        "likes",
        "comments",
        "shares",
        "saved",
        "total_interactions",
        "impressions",
        "engagement",
        "video_views",
    ]

    rows = []
    for index, item in enumerate(media, start=1):
        media_id = item.get("id", "")
        media_type = item.get("media_type", "")
        print(f"Instagram: media {index}/{total} ({media_type}) id={media_id}", flush=True)
        metrics, errors = fetch_supported_metrics(
            client,
            item["id"],
            insight_candidates,
            period=None,
            since=since,
            until=until,
        )
        row = {
            "platform": "instagram",
            "object_level": "media",
            "id": item.get("id", ""),
            "timestamp": item.get("timestamp", ""),
            "username": item.get("username", ""),
            "caption": clean_text(item.get("caption")),
            "media_type": item.get("media_type", ""),
            "media_product_type": item.get("media_product_type", ""),
            "permalink": item.get("permalink", ""),
            "media_url": item.get("media_url", ""),
            "thumbnail_url": item.get("thumbnail_url", ""),
            "like_count": item.get("like_count", ""),
            "comments_count": item.get("comments_count", ""),
            "metric_errors": json.dumps(errors, ensure_ascii=False, sort_keys=True),
        }
        row.update({f"insight_{key}": value for key, value in metrics.items()})
        rows.append(row)
        time.sleep(0.2)

    return rows


def export_facebook(client, fb_page_id, limit, since=None, until=None):
    print(f"Facebook: mengambil daftar post, maksimal {limit} item...", flush=True)
    post_fields = "id,message,created_time,permalink_url"
    params = {"fields": post_fields, "limit": min(limit, 100)}
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    try:
        posts = client.get_all_pages(f"{fb_page_id}/posts", params=params)[:limit]
    except MetaApiError as exc:
        print(f"Facebook: endpoint /posts gagal ({exc}). Mencoba /feed...", flush=True)
        posts = client.get_all_pages(f"{fb_page_id}/feed", params=params)[:limit]

    total = len(posts)
    print(f"Facebook: ditemukan {total} post. Mulai ambil insight per post.", flush=True)

    insight_candidates = [
        "post_impressions",
        "post_impressions_unique",
        "post_engaged_users",
        "post_clicks",
        "post_reactions_by_type_total",
        "post_video_views",
    ]

    rows = []
    for index, post in enumerate(posts, start=1):
        post_id = post.get("id", "")
        created_time = post.get("created_time", "")
        print(f"Facebook: post {index}/{total} ({created_time}) id={post_id}", flush=True)

        extra = {}
        extra_errors = {}
        try:
            extra = client.get(
                post_id,
                {
                    "fields": (
                        "full_picture,shares,comments.summary(true),"
                        "reactions.summary(true)"
                    )
                },
            )
        except MetaApiError as exc:
            extra_errors["post_extra_fields"] = str(exc)

        metrics, errors = fetch_supported_metrics(client, post["id"], insight_candidates)
        reactions = extra.get("reactions", {}).get("summary", {})
        comments = extra.get("comments", {}).get("summary", {})
        shares = extra.get("shares", {})
        errors.update(extra_errors)
        row = {
            "platform": "facebook",
            "object_level": "post",
            "id": post.get("id", ""),
            "created_time": post.get("created_time", ""),
            "message": clean_text(post.get("message")),
            "permalink_url": post.get("permalink_url", ""),
            "full_picture": extra.get("full_picture", ""),
            "reaction_count": reactions.get("total_count", ""),
            "comment_count": comments.get("total_count", ""),
            "share_count": shares.get("count", ""),
            "metric_errors": json.dumps(errors, ensure_ascii=False, sort_keys=True),
        }
        row.update({f"insight_{key}": value for key, value in metrics.items()})
        rows.append(row)
        time.sleep(0.2)

    return rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export data Instagram Business dan Facebook Page ke CSV bersih."
    )
    parser.add_argument(
        "--platform",
        choices=["all", "instagram", "facebook", "diagnose"],
        default="all",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Jumlah maksimal media/post yang diambil. Default 25 agar eksperimen tidak terlalu lama.",
    )
    parser.add_argument("--since", help="Tanggal awal atau Unix timestamp, contoh: 2026-05-01")
    parser.add_argument("--until", help="Tanggal akhir atau Unix timestamp, contoh: 2026-05-13")
    parser.add_argument("--output-dir", default="data/processed")
    return parser.parse_args()


def main():
    try:
        load_dotenv()
        args = parse_args()
        token = env_required("META_ACCESS_TOKEN")
        api_version = os.environ.get("META_API_VERSION", DEFAULT_API_VERSION).strip()
        fb_page_id = os.environ.get("FB_PAGE_ID", "").strip()
        ig_business_id = os.environ.get("IG_BUSINESS_ID", "").strip()
        client = MetaClient(token, api_version)
        output_dir = Path(args.output_dir)
        run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if args.platform == "diagnose":
            checks = diagnose(client, fb_page_id=fb_page_id, ig_business_id=ig_business_id)
            path = output_dir / f"meta_diagnose_{run_stamp}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Wrote {path}")
            return

        exported = []

        if args.platform in ("all", "instagram"):
            if not ig_business_id:
                print("Skip Instagram: IG_BUSINESS_ID is not set.", file=sys.stderr)
            else:
                rows = export_instagram(client, ig_business_id, args.limit, args.since, args.until)
                path = output_dir / f"instagram_media_{run_stamp}.csv"
                write_csv(path, rows)
                exported.append(path)

        if args.platform in ("all", "facebook"):
            if not fb_page_id:
                print("Skip Facebook: FB_PAGE_ID is not set.", file=sys.stderr)
            else:
                rows = export_facebook(client, fb_page_id, args.limit, args.since, args.until)
                path = output_dir / f"facebook_posts_{run_stamp}.csv"
                write_csv(path, rows)
                exported.append(path)

        for path in exported:
            print(f"Wrote {path}")
    except MetaApiError as exc:
        print(f"Meta API error: {exc}", file=sys.stderr)
        print("Cek lagi META_ACCESS_TOKEN, FB_PAGE_ID/IG_BUSINESS_ID, permission, dan masa berlaku token.", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
