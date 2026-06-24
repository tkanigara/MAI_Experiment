import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from secret_manager import hydrate_env_from_secret

DEFAULT_API_VERSION = "v23.0"


class MetaApiError(Exception):
    """Raised when Meta Graph API returns an unusable response."""


def load_dotenv(path=".env"):
    """Load a small .env file without overriding existing environment values."""
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class MetaClient:
    """Thin wrapper for Meta Graph API GET requests."""

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
    hydrate_env_from_secret(name)
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing environment variable: {name}")
    return value


def clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def dumps_raw(value):
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def metric_value(insights_payload, metric_name):
    """Extract the direct metric value from a Meta /insights response."""
    for item in insights_payload.get("data", []):
        if item.get("name") != metric_name:
            continue

        if "total_value" in item:
            total_value = item.get("total_value", {})
            if "value" in total_value:
                return total_value.get("value", "")

        values = item.get("values", [])
        if not values:
            return ""
        value = values[-1].get("value", "")
        if isinstance(value, dict):
            return dumps_raw(value)
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
    """Fetch supported metrics, falling back per metric when Meta rejects a group."""
    results = {}
    errors = {}
    raw_payloads = {}

    try:
        payload = fetch_metric_group(client, object_id, candidates, period, since, until)
        raw_payloads["group"] = payload
        for metric in candidates:
            results[metric] = metric_value(payload, metric)
        return results, errors, raw_payloads
    except MetaApiError as exc:
        errors["group"] = str(exc)

    for metric in candidates:
        try:
            payload = fetch_metric_group(client, object_id, [metric], period, since, until)
            raw_payloads[metric] = payload
            results[metric] = metric_value(payload, metric)
        except MetaApiError as exc:
            errors[metric] = str(exc)

    return results, errors, raw_payloads


def write_csv(path, rows):
    """Write raw CSV with stable important columns first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = [
        "platform",
        "object_level",
        "report_month",
        "report_since",
        "report_until",
        "id",
        "snapshot_date",
        "snapshot_time",
        "timestamp",
        "media_type",
        "media_product_type",
        "permalink",
        "media_url",
        "thumbnail_url",
        "like_count",
        "comments_count",
        "insight_views",
        "insight_reach",
        "insight_likes",
        "insight_comments",
        "insight_reposts",
        "insight_shares",
        "insight_saved",
        "insight_total_interactions",
        "audience_demographic_source",
        "account_raw_demographic_age_gender",
        "account_raw_demographic_country",
        "account_raw_reached_demographic_age_gender",
        "account_raw_reached_demographic_country",
    ]
    ordered = [key for key in preferred if key in fieldnames]
    ordered.extend(key for key in fieldnames if key not in ordered)

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=ordered)
        writer.writeheader()
        writer.writerows(rows)


def fetch_instagram_demographic(client, ig_business_id, metric, breakdown, timeframe=None):
    params = {
        "metric": metric,
        "period": "lifetime",
        "metric_type": "total_value",
        "breakdown": breakdown,
    }
    if timeframe:
        params["timeframe"] = timeframe
    return client.get(f"{ig_business_id}/insights", params=params)


def export_instagram_account(client, ig_business_id, since=None, until=None):
    print("Instagram: mengambil account profile dan account-level insights...", flush=True)
    snapshot_time = datetime.now(timezone.utc).isoformat()
    snapshot_date = snapshot_time[:10]

    profile = client.get(
        ig_business_id,
        {
            "fields": (
                "id,username,name,followers_count,"
                "follows_count,media_count,profile_picture_url"
            )
        },
    )

    errors = {}
    demographic_payloads = {}
    for key, metric, breakdown, timeframe in [
        ("demographic_age_gender", "follower_demographics", "age,gender", None),
        ("demographic_country", "follower_demographics", "country", None),
        ("reached_demographic_age_gender", "reached_audience_demographics", "age,gender", "last_30_days"),
        ("reached_demographic_country", "reached_audience_demographics", "country", "last_30_days"),
    ]:
        try:
            demographic_payloads[key] = fetch_instagram_demographic(
                client,
                ig_business_id,
                metric,
                breakdown,
                timeframe=timeframe,
            )
        except MetaApiError as exc:
            errors[key] = str(exc)

    row = {
        "platform": "instagram",
        "object_level": "account",
        "snapshot_date": snapshot_date,
        "snapshot_time": snapshot_time,
        "id": profile.get("id", ""),
        "username": profile.get("username", ""),
        "name": profile.get("name", ""),
        "followers_count": profile.get("followers_count", ""),
        "follows_count": profile.get("follows_count", ""),
        "media_count": profile.get("media_count", ""),
        "profile_picture_url": profile.get("profile_picture_url", ""),
    }
    row.update({f"raw_{key}": dumps_raw(value) for key, value in demographic_payloads.items()})
    return [row]


def media_in_period(item, since=None, until=None):

    if not since and not until:

        return True

    timestamp = item.get("timestamp", "")

    if not timestamp:

        return False

    try:

        posted_date = datetime.strptime(

            timestamp,

            "%Y-%m-%dT%H:%M:%S%z"

        ).date()

    except Exception as e:

        print("TIMESTAMP ERROR:", timestamp, e)

        return False

    if since and posted_date < datetime.fromisoformat(since).date():

        return False

    if until and posted_date > datetime.fromisoformat(until).date():

        return False

    return True


def export_instagram(client, ig_business_id, limit, since=None, until=None):
    print(f"Instagram: mengambil daftar media, maksimal {limit} item...", flush=True)
    media_fields = (
        "id,media_type,media_product_type,media_url,permalink,"
        "thumbnail_url,timestamp,username,like_count,comments_count"
    )
    media = client.get_all_pages(
        f"{ig_business_id}/media",
        params={"fields": media_fields, "limit": min(limit, 100)},
    )
    print("=========== DEBUG ============")
    for item in media[:10]:
        print(
            "MEDIA: ",
            item.get("id"),
            item.get("timestamp"),
            item.get("media_type")
        )
    if since or until:
        media = [item for item in media if media_in_period(item, since, until)]
    media = media[:limit]
    total = len(media)
    print(f"Instagram: ditemukan {total} media. Mulai ambil insight per media.", flush=True)

    insight_candidates = [
        "views",
        "reach",
        "likes",
        "comments",
        "reposts",
        "shares",
        "saved",
        "total_interactions",
    ]

    rows = []
    for index, item in enumerate(media, start=1):
        media_id = item.get("id", "")
        media_type = item.get("media_type", "")
        print(f"Instagram: media {index}/{total} ({media_type}) id={media_id}", flush=True)
        metrics, errors, _raw_payloads = fetch_supported_metrics(
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
            "media_type": item.get("media_type", ""),
            "media_product_type": item.get("media_product_type", ""),
            "permalink": item.get("permalink", ""),
            "media_url": item.get("media_url", ""),
            "thumbnail_url": item.get("thumbnail_url", ""),
            "like_count": item.get("like_count", ""),
            "comments_count": item.get("comments_count", ""),
        }
        row.update({f"insight_{key}": value for key, value in metrics.items()})
        rows.append(row)
        time.sleep(0.2)

    return rows
