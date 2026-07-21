from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock

import requests as http_requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from generate_slides_example import (  # noqa: E402
    copy_template,
    extract_presentation_id,
    get_google_services,
    image_placeholder_mapping,
)


PLATFORM_TABLES = {
    "instagram": "instagram_reports",
    "facebook": "facebook_reports",
    "tiktok": "tiktok_reports",
    "youtube": "youtube_reports",
}

PLATFORM_PREFIXES = {
    "instagram": "IG",
    "facebook": "FB",
    "tiktok": "TK",
    "youtube": "YT",
}

PLATFORM_LABELS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "youtube": "YouTube",
}

PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Za-z0-9_]+\}\}")
TEMPLATE_PLACEHOLDER_CACHE: dict[str, set[str]] = {}
_SLIDES_WRITE_LOCK = Lock()
_SLIDES_LAST_WRITE_AT = 0.0

# Internal quota safeguards. These are implementation details rather than
# deployment settings, so keep them out of .env unless they become operational
# tuning knobs later.
SLIDES_WRITE_MIN_INTERVAL_SECONDS = 1.05
SLIDES_API_MAX_RETRIES = 2
SLIDES_QUOTA_RETRY_SECONDS = 65.0
SLIDES_IMAGE_PREFLIGHT_ENABLED = True
SLIDES_IMAGE_VALIDATION_WORKERS = 8
SLIDES_IMAGE_CONNECT_TIMEOUT_SECONDS = 3.0
SLIDES_IMAGE_READ_TIMEOUT_SECONDS = 8.0
SLIDES_IMAGE_MAX_API_CALLS = 20
SLIDES_IMAGE_RETRY_INDIVIDUAL = False
SLIDES_STRUCTURED_TEXT_OCCURRENCES_PER_BATCH = 200


class StepProfiler:
    def __init__(self):
        self.started_at = time.perf_counter()
        self.steps: dict[str, float] = {}

    def record(self, name: str, start: float):
        duration = time.perf_counter() - start
        self.steps[name] = self.steps.get(name, 0) + duration
        print(f"[slides] {name}: {duration:.2f}s", flush=True)

    def total(self) -> float:
        duration = time.perf_counter() - self.started_at
        self.steps["total"] = duration
        print(f"[slides] total: {duration:.2f}s", flush=True)
        return duration


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def execute_slides_batch_update(
    slides_service,
    presentation_id: str,
    batch_requests: list[dict],
) -> dict:
    """Serialize and pace Slides writes so one report cannot burst the user quota."""
    global _SLIDES_LAST_WRITE_AT

    if not batch_requests:
        return {"replies": []}

    min_interval = SLIDES_WRITE_MIN_INTERVAL_SECONDS
    max_retries = SLIDES_API_MAX_RETRIES
    quota_retry_seconds = SLIDES_QUOTA_RETRY_SECONDS

    for attempt in range(max_retries + 1):
        try:
            with _SLIDES_WRITE_LOCK:
                elapsed = time.monotonic() - _SLIDES_LAST_WRITE_AT
                if _SLIDES_LAST_WRITE_AT and elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                try:
                    return (
                        slides_service.presentations()
                        .batchUpdate(
                            presentationId=presentation_id,
                            body={"requests": batch_requests},
                        )
                        .execute()
                    )
                finally:
                    _SLIDES_LAST_WRITE_AT = time.monotonic()
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status != 429 or attempt >= max_retries:
                raise

            response_headers = getattr(exc, "resp", None)
            retry_after = None
            if response_headers is not None:
                try:
                    retry_after = float(response_headers.get("retry-after", 0) or 0)
                except (TypeError, ValueError, AttributeError):
                    retry_after = None
            delay = max(retry_after or 0, quota_retry_seconds * (attempt + 1))
            print(
                f"[slides_report] Slides quota reached; retrying batch in {delay:.0f}s "
                f"(attempt {attempt + 1}/{max_retries})",
                flush=True,
            )
            time.sleep(delay)

    raise RuntimeError("Slides batch update retry loop ended unexpectedly")


def validate_image_urls(image_mapping: dict[str, str]) -> dict[str, tuple[bool, str]]:
    """Check public image URLs concurrently before spending Slides write calls."""
    unique_urls = sorted({str(value).strip() for value in image_mapping.values() if value})
    if not unique_urls:
        return {}

    connect_timeout = SLIDES_IMAGE_CONNECT_TIMEOUT_SECONDS
    read_timeout = SLIDES_IMAGE_READ_TIMEOUT_SECONDS
    worker_count = min(SLIDES_IMAGE_VALIDATION_WORKERS, len(unique_urls))
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MAI-Slides-Image-Validator/1.0)",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    def validate(url: str) -> tuple[bool, str]:
        if not url.lower().startswith(("http://", "https://")):
            return False, "URL must use http or https"
        try:
            with http_requests.get(
                url,
                headers=headers,
                stream=True,
                allow_redirects=True,
                timeout=(connect_timeout, read_timeout),
            ) as response:
                if not 200 <= response.status_code < 300:
                    return False, f"HTTP {response.status_code}"
                content_type = response.headers.get("content-type", "").lower()
                if content_type and not (
                    content_type.startswith("image/")
                    or "application/octet-stream" in content_type
                ):
                    return False, f"unsupported content type {content_type.split(';')[0]}"
                return True, "ok"
        except http_requests.RequestException as exc:
            return False, exc.__class__.__name__

    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(validate, url): url for url in unique_urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                results[url] = (False, exc.__class__.__name__)
    return results


def database_url() -> str:
    load_dotenv(BASE_DIR / ".env")
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://mai_user:mai_password@localhost:55432/mai_socmed_report",
    )


def default_template() -> str:
    return (
        os.getenv("SLIDES_TEMPLATE_ID")
        or os.getenv("GOOGLE_SLIDES_TEMPLATE_ID")
        or ""
    )


def default_credentials() -> str:
    auth_mode = os.getenv("GOOGLE_SLIDES_AUTH", "").strip().lower()
    if auth_mode in {"oauth", "user_oauth", "user-oauth"}:
        return os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    return (
        os.getenv("GOOGLE_SLIDES_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    )


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def fmt_number(value, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def fmt_percent(value, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    return f"{fmt_number(value)}%"


def pct(actual, target) -> str:
    try:
        actual_number = float(actual)
        target_number = float(target)
    except (TypeError, ValueError):
        return "-"
    if target_number == 0:
        return "-"
    return fmt_percent(round((actual_number / target_number) * 100, 2))


def clean_text(value, limit: int | None = None) -> str:
    text_value = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text_value or text_value == "-":
        return "-"
    if limit and len(text_value) > limit:
        return text_value[: max(limit - 3, 0)].rstrip() + "..."
    return text_value


def placeholder(name: str) -> str:
    return "{{" + name + "}}"


def is_image_placeholder_key(key: str) -> bool:
    return key.strip("{}").endswith("_IMAGE")


def row_dict(row):
    return dict(row) if row else None


def content_identity(post: dict) -> tuple:
    if post.get("post_id"):
        return ("post_id", str(post["post_id"]))
    if post.get("permalink"):
        return ("permalink", str(post["permalink"]))
    return (
        "content",
        str(post.get("caption") or ""),
        str(post.get("published_at") or ""),
    )


def name_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(value or "").lower()) if token]


def normalized_name(value: str) -> str:
    return "".join(name_tokens(value))


def client_self_terms(client: dict, profiles: list[dict] | None = None) -> dict:
    long_terms = set()
    short_terms = set()
    candidates = [
        client.get("client_code"),
        client.get("client_name"),
    ]
    for profile in profiles or []:
        candidates.extend(
            [
                profile.get("profile_name"),
                profile.get("source_profile_id"),
                profile.get("profile_url"),
            ]
        )

    for candidate in candidates:
        tokens = name_tokens(candidate)
        normalized = normalized_name(candidate)
        if not normalized:
            continue
        if len(normalized) <= 4:
            short_terms.add(normalized)
        else:
            long_terms.add(normalized)
        descriptive_tokens = [token for token in tokens if len(token) > 3]
        if len(descriptive_tokens) >= 2:
            long_terms.add("".join(descriptive_tokens))

    client_name_tokens = name_tokens(client.get("client_name"))
    if len(client_name_tokens) >= 2:
        acronym = "".join(token[0] for token in client_name_tokens if token)
        if acronym:
            short_terms.add(acronym)

    return {"long": long_terms, "short": short_terms}


def is_self_profile(row: dict, self_terms: dict) -> bool:
    values = [
        row.get("profile_name"),
        row.get("profile_url"),
        row.get("source_profile_id"),
    ]
    for value in values:
        tokens = set(name_tokens(value))
        normalized = normalized_name(value)
        if not normalized:
            continue
        if any(term in normalized or normalized in term for term in self_terms.get("long", set())):
            return True
        if tokens & self_terms.get("short", set()):
            return True
    return False


def iter_page_elements(page_elements: list[dict]):
    for element in page_elements:
        yield element
        children = element.get("elementGroup", {}).get("children", [])
        if children:
            yield from iter_page_elements(children)


def text_with_api_boundaries(text_elements: list[dict]) -> tuple[str, list[int]]:
    """Reconstruct text while preserving Google Slides UTF-16 indices."""
    characters = []
    api_boundaries = []
    cursor = 0
    for element in text_elements:
        text_run = element.get("textRun")
        if not text_run:
            continue
        content = str(text_run.get("content", ""))
        start_index = element.get("startIndex")
        if start_index is not None:
            cursor = int(start_index)
        for character in content:
            characters.append(character)
            api_boundaries.append(cursor)
            cursor += len(character.encode("utf-16-le")) // 2
    api_boundaries.append(cursor)
    return "".join(characters), api_boundaries


def iter_text_containers(presentation: dict):
    for slide in presentation.get("slides", []):
        for element in iter_page_elements(slide.get("pageElements", [])):
            object_id = element.get("objectId")
            if not object_id:
                continue
            shape_text = element.get("shape", {}).get("text", {}).get("textElements", [])
            if shape_text:
                yield object_id, None, shape_text

            table = element.get("table", {})
            for row_index, row in enumerate(table.get("tableRows", [])):
                for column_index, cell in enumerate(row.get("tableCells", [])):
                    cell_text = cell.get("text", {}).get("textElements", [])
                    if cell_text:
                        yield (
                            object_id,
                            {
                                "rowIndex": row_index,
                                "columnIndex": column_index,
                            },
                            cell_text,
                        )


def extract_placeholders_from_presentation(presentation: dict) -> set[str]:
    placeholders = set(
        PLACEHOLDER_PATTERN.findall(json.dumps(presentation, ensure_ascii=False))
    )
    for _object_id, _cell_location, text_elements in iter_text_containers(presentation):
        text_value, _boundaries = text_with_api_boundaries(text_elements)
        placeholders.update(PLACEHOLDER_PATTERN.findall(text_value))
    return placeholders


def structured_text_replacement_operations(
    presentation: dict,
    mapping: dict,
    skip_placeholders: set[str] | None = None,
) -> tuple[list[list[dict]], list[str]]:
    skip_placeholders = skip_placeholders or set()
    operations = []
    replaced_keys = []

    for object_id, cell_location, text_elements in iter_text_containers(presentation):
        text_value, api_boundaries = text_with_api_boundaries(text_elements)
        matches = [
            match
            for match in PLACEHOLDER_PATTERN.finditer(text_value)
            if match.group(0) in mapping and match.group(0) not in skip_placeholders
        ]
        for match in reversed(matches):
            placeholder_key = match.group(0)
            start_index = api_boundaries[match.start()]
            end_index = api_boundaries[match.end()]
            replacement = mapping.get(placeholder_key, "-")
            if is_image_placeholder_key(placeholder_key):
                replacement = "-"

            delete_text = {
                "objectId": object_id,
                "textRange": {
                    "type": "FIXED_RANGE",
                    "startIndex": start_index,
                    "endIndex": end_index,
                },
            }
            insert_text = {
                "objectId": object_id,
                "insertionIndex": start_index,
                "text": str(replacement),
            }
            if cell_location is not None:
                delete_text["cellLocation"] = cell_location
                insert_text["cellLocation"] = cell_location

            operations.append(
                [
                    {"deleteText": delete_text},
                    {"insertText": insert_text},
                ]
            )
            replaced_keys.append(placeholder_key)
    return operations, replaced_keys


def replace_structured_text_placeholders(
    slides_service,
    presentation_id: str,
    mapping: dict,
    skip_placeholders: set[str] | None = None,
) -> dict:
    """Replace placeholders split across multiple formatted text runs."""
    presentation = (
        slides_service.presentations()
        .get(presentationId=presentation_id)
        .execute()
    )
    operations, replaced_keys = structured_text_replacement_operations(
        presentation,
        mapping,
        skip_placeholders=skip_placeholders,
    )
    batch_size = SLIDES_STRUCTURED_TEXT_OCCURRENCES_PER_BATCH
    batch_sizes = []
    for index in range(0, len(operations), batch_size):
        operation_batch = operations[index : index + batch_size]
        requests = [request for operation in operation_batch for request in operation]
        batch_sizes.append(len(operation_batch))
        execute_slides_batch_update(slides_service, presentation_id, requests)
        print(
            "[slides_report] structuredText "
            f"batch={len(batch_sizes)} occurrences={len(operation_batch)} "
            f"requests={len(requests)}",
            flush=True,
        )
    print(
        "[slides_report] structuredText "
        f"totalOccurrences={len(replaced_keys)} totalBatches={len(batch_sizes)}",
        flush=True,
    )
    return {
        "sent_keys": replaced_keys,
        "sent_key_count": len(replaced_keys),
        "unique_key_count": len(set(replaced_keys)),
        "batch_count": len(batch_sizes),
        "batch_sizes": batch_sizes,
        "total_requests": len(replaced_keys) * 2,
    }


def fetch_presentation_placeholders(slides_service, presentation_id: str) -> set[str]:
    if presentation_id in TEMPLATE_PLACEHOLDER_CACHE:
        return set(TEMPLATE_PLACEHOLDER_CACHE[presentation_id])
    presentation = (
        slides_service.presentations()
        .get(presentationId=presentation_id)
        .execute()
    )
    placeholders = extract_placeholders_from_presentation(presentation)
    TEMPLATE_PLACEHOLDER_CACHE[presentation_id] = set(placeholders)
    return placeholders


def image_object_ids_by_placeholder(slides_service, presentation_id: str, image_mapping: dict) -> dict[str, list[str]]:
    presentation = (
        slides_service.presentations()
        .get(presentationId=presentation_id)
        .execute()
    )
    matched = {key: [] for key in image_mapping}
    for slide in presentation.get("slides", []):
        for element in slide.get("pageElements", []):
            if "image" not in element:
                continue
            object_id = element.get("objectId")
            alt_text = " ".join(
                str(element.get(field, "") or "")
                for field in ("title", "description")
            )
            for placeholder_key in image_mapping:
                if object_id and placeholder_key in alt_text:
                    matched[placeholder_key].append(object_id)
    return matched


def replace_image_placeholders_safe(
    slides_service,
    presentation_id: str,
    image_mapping: dict,
    allowed_placeholders: set[str] | None = None,
) -> dict:
    template_filtered_mapping = {
        key: value
        for key, value in image_mapping.items()
        if allowed_placeholders is None or key in allowed_placeholders
    }
    skipped_non_template = sorted(set(image_mapping) - set(template_filtered_mapping))
    attempted_total = len(template_filtered_mapping)
    if not template_filtered_mapping:
        print("[slides_report] image replacement: no template image placeholders with valid URLs", flush=True)
        return {
            "attempted": 0,
            "replaced": [],
            "failed": [],
            "unmatched": [],
            "skipped_non_template": skipped_non_template,
        }

    failed = []
    filtered_mapping = dict(template_filtered_mapping)
    if SLIDES_IMAGE_PREFLIGHT_ENABLED:
        validation = validate_image_urls(filtered_mapping)
        invalid_keys = []
        for placeholder_key, image_url in filtered_mapping.items():
            valid, reason = validation.get(str(image_url).strip(), (False, "validation unavailable"))
            if valid:
                continue
            invalid_keys.append(placeholder_key)
            failed.append(
                {
                    "placeholder": placeholder_key,
                    "method": "preflight",
                    "reason": reason,
                }
            )
        for placeholder_key in invalid_keys:
            filtered_mapping.pop(placeholder_key, None)
        print(
            "[slides_report] image preflight: "
            f"checked={attempted_total} valid={len(filtered_mapping)} invalid={len(invalid_keys)}",
            flush=True,
        )

    if not filtered_mapping:
        print(
            "[slides_report] image replacement: no publicly accessible image URLs",
            flush=True,
        )
        return {
            "attempted": attempted_total,
            "replaced": [],
            "failed": failed,
            "unmatched": [],
            "skipped_non_template": skipped_non_template,
            "object_api_calls": 0,
            "image_api_calls": 0,
        }

    image_object_ids = image_object_ids_by_placeholder(
        slides_service,
        presentation_id,
        filtered_mapping,
    )
    replaced = []
    replaced_object_ids = []
    chunk_size = env_int("SLIDES_IMAGE_BATCH_SIZE", 20)
    max_image_api_calls = SLIDES_IMAGE_MAX_API_CALLS

    object_requests = []
    object_request_meta = []
    for placeholder_key, object_ids in image_object_ids.items():
        for object_id in object_ids:
            object_requests.append(
                {
                    "replaceImage": {
                        "imageObjectId": object_id,
                        "url": filtered_mapping[placeholder_key],
                        "imageReplaceMethod": "CENTER_INSIDE",
                    }
                }
            )
            object_request_meta.append((placeholder_key, object_id))

    object_api_calls = 0
    image_api_calls = 0

    def execute_image_batch(batch):
        nonlocal image_api_calls
        if image_api_calls >= max_image_api_calls:
            raise RuntimeError(
                f"image API call budget exceeded ({max_image_api_calls})"
            )
        image_api_calls += 1
        return execute_slides_batch_update(
            slides_service,
            presentation_id,
            batch,
        )

    def execute_object_batch(batch, batch_meta):
        nonlocal object_api_calls
        if not batch:
            return
        object_api_calls += 1
        try:
            execute_image_batch(batch)
            for placeholder_key, object_id in batch_meta:
                replaced.append(placeholder_key)
                replaced_object_ids.append(object_id)
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            # A single inaccessible CDN URL invalidates the complete Slides
            # batch. Split only client errors so valid images can still pass;
            # retrying 429/5xx by subdivision would only consume more quota.
            if len(batch) > 1 and status == 400:
                midpoint = len(batch) // 2
                execute_object_batch(batch[:midpoint], batch_meta[:midpoint])
                execute_object_batch(batch[midpoint:], batch_meta[midpoint:])
                return
            reason = str(exc).splitlines()[0]
            for placeholder_key, _object_id in batch_meta:
                failed.append(
                    {
                        "placeholder": placeholder_key,
                        "method": "replaceImage",
                        "reason": reason,
                    }
                )

    for index in range(0, len(object_requests), chunk_size):
        execute_object_batch(
            object_requests[index : index + chunk_size],
            object_request_meta[index : index + chunk_size],
        )

    fallback_requests = []
    fallback_request_meta = []
    for placeholder_key, image_url in filtered_mapping.items():
        if image_object_ids.get(placeholder_key):
            continue
        fallback_requests.append(
            {
                "replaceAllShapesWithImage": {
                    "containsText": {
                        "text": placeholder_key,
                        "matchCase": True,
                    },
                    "imageUrl": image_url,
                    "replaceMethod": "CENTER_INSIDE",
                }
            }
        )
        fallback_request_meta.append(placeholder_key)

    for index in range(0, len(fallback_requests), chunk_size):
        batch = fallback_requests[index : index + chunk_size]
        batch_meta = fallback_request_meta[index : index + chunk_size]
        try:
            response = execute_image_batch(batch)
            replies = response.get("replies", [])
            for placeholder_key, reply in zip(batch_meta, replies):
                occurrences = (
                    reply
                    .get("replaceAllShapesWithImage", {})
                    .get("occurrencesChanged", 0)
                )
                if occurrences:
                    replaced.append(placeholder_key)
        except Exception as exc:
            reason = str(exc).splitlines()[0]
            for placeholder_key in batch_meta:
                failed.append(
                    {
                        "placeholder": placeholder_key,
                        "method": "replaceAllShapesWithImage",
                        "reason": reason,
                    }
                )

    # If a batched fallback failed because of a bad URL, retry each item once so
    # one inaccessible CDN URL does not block all other images in the same batch.
    retry_placeholders = {
        item["placeholder"]
        for item in failed
        if item["method"] == "replaceAllShapesWithImage"
    } - set(replaced)
    retry_individual = SLIDES_IMAGE_RETRY_INDIVIDUAL
    if retry_placeholders and retry_individual:
        failed = [
            item
            for item in failed
            if not (
                item["method"] == "replaceAllShapesWithImage"
                and item["placeholder"] in retry_placeholders
            )
        ]
    for placeholder_key in sorted(retry_placeholders if retry_individual else []):
        request = {
            "replaceAllShapesWithImage": {
                "containsText": {
                    "text": placeholder_key,
                    "matchCase": True,
                },
                "imageUrl": filtered_mapping[placeholder_key],
                "replaceMethod": "CENTER_INSIDE",
            }
        }
        try:
            response = execute_image_batch([request])
            occurrences = (
                response.get("replies", [{}])[0]
                .get("replaceAllShapesWithImage", {})
                .get("occurrencesChanged", 0)
            )
            if occurrences:
                replaced.append(placeholder_key)
        except Exception as exc:
            failed.append(
                {
                    "placeholder": placeholder_key,
                    "method": "replaceAllShapesWithImage",
                    "reason": str(exc).splitlines()[0],
                }
            )

    replaced_set = set(replaced)
    matched_object_keys = {
        key
        for key, object_ids in image_object_ids.items()
        if object_ids
    }
    unmatched = sorted(set(filtered_mapping) - replaced_set - matched_object_keys)
    print(
        "[slides_report] image replacement: "
        f"attempted={attempted_total} replaced={len(replaced_set)} "
        f"failed={len(failed)} unmatched={len(unmatched)} "
        f"objectApiCalls={object_api_calls} imageApiCalls={image_api_calls}",
        flush=True,
    )
    for item in failed[:10]:
        print(
            f"[slides_report] image failed {item['placeholder']} via {item['method']}: {item['reason']}",
            flush=True,
        )
    if replaced_object_ids and env_bool("SLIDES_CLEAN_IMAGE_ALT_TEXT", False):
        clear_requests = [
            {
                "updatePageElementAltText": {
                    "objectId": object_id,
                    "title": "",
                    "description": "",
                }
            }
            for object_id in replaced_object_ids
        ]
        try:
            execute_image_batch(clear_requests)
        except Exception as exc:
            print(
                f"[slides_report] image alt text cleanup skipped: {str(exc).splitlines()[0]}",
                flush=True,
            )
    return {
        "attempted": attempted_total,
        "replaced": sorted(replaced_set),
        "failed": failed,
        "unmatched": unmatched,
        "skipped_non_template": skipped_non_template,
        "object_api_calls": object_api_calls,
        "image_api_calls": image_api_calls,
    }


def fallback_value(value) -> bool:
    return value is None or str(value).strip() in {"", "-"}


def platform_from_placeholder(placeholder_name: str) -> str | None:
    if placeholder_name.startswith("IG_") or "_IG_" in placeholder_name:
        return "instagram"
    if placeholder_name.startswith("FB_") or "_FB_" in placeholder_name:
        return "facebook"
    if placeholder_name.startswith("TK_") or "_TK_" in placeholder_name:
        return "tiktok"
    if placeholder_name.startswith("YT_") or "_YT_" in placeholder_name:
        return "youtube"
    return None


def issue_reason(placeholder_key: str, mapping: dict, payload: dict | None = None, sent_keys: set[str] | None = None) -> str:
    if placeholder_key not in mapping:
        return "placeholder not found in mapping; template name may have changed or alias is missing"
    if sent_keys is not None and placeholder_key not in sent_keys:
        return "mapping exists but was not included in batchUpdate"

    value = mapping.get(placeholder_key)
    if not fallback_value(value):
        return "mapping exists and was sent to Slides API; replacement did not apply, so inspect split text runs or batchUpdate result"

    name = placeholder_key.strip("{}")
    platform = platform_from_placeholder(name)
    if "POST_TOP" in name or "POST_LOW" in name:
        bucket = "top" if "POST_TOP" in name else "low"
        if payload and platform:
            posts = (payload.get("content", {}).get(platform, {}) or {}).get(bucket, [])
            if not posts:
                return f"mapping fallback '-' because no {bucket} content rows were found in social_content_reports"
        return "mapping fallback '-' because content field is unavailable for this post slot"
    if "COMP" in name:
        if payload and platform and not payload.get("competitors", {}).get(platform):
            return "mapping fallback '-' because no competitor rows were found in competitor_profile_reports"
        return "mapping fallback '-' because competitor field is unavailable"
    if "DEMOGRAPHIC" in name or name.startswith("AGE_") or name.startswith("GENDER_") or name.startswith("TOP_CITY_"):
        return "mapping fallback '-' because demographics data is empty or not imported"
    if name.startswith("WEB_") or name.startswith("SSL_") or name.startswith("DOMAIN_"):
        return "mapping fallback '-' because website/SEO data is not imported yet"
    if name.startswith("ADS_"):
        return "mapping fallback '-' because paid ads data is not imported yet"
    if platform:
        report = (payload or {}).get("reports", {}).get(platform) if payload else None
        if not report:
            return f"mapping fallback '-' because no {platform} report row exists for this period"
        return f"mapping fallback '-' because source DB value is NULL or empty for {platform}"
    return "mapping fallback '-' because source data is unavailable"


def audit_mapping(template_placeholders: set[str], mapping: dict, payload: dict | None = None, sent_keys: set[str] | None = None, remaining_placeholders: set[str] | None = None) -> dict:
    mapping_keys = set(mapping)
    matched = sorted(template_placeholders & mapping_keys)
    missing = sorted(template_placeholders - mapping_keys)
    unused = sorted(mapping_keys - template_placeholders)
    fallback_keys = sorted(
        key for key in matched
        if fallback_value(mapping.get(key))
    )
    remaining = sorted(remaining_placeholders or [])
    return {
        "template_placeholder_count": len(template_placeholders),
        "mapping_key_count": len(mapping_keys),
        "matched_count": len(matched),
        "missing_in_mapping_count": len(missing),
        "unused_mapping_key_count": len(unused),
        "remaining_placeholder_count": len(remaining),
        "matched_placeholders": matched,
        "missing_in_mapping": [
            {"placeholder": key, "reason": issue_reason(key, mapping, payload, sent_keys)}
            for key in missing
        ],
        "unused_mapping_keys": unused,
        "fallback_values": [
            {"placeholder": key, "value": mapping.get(key), "reason": issue_reason(key, mapping, payload, sent_keys)}
            for key in fallback_keys
        ],
        "remaining_placeholders": [
            {"placeholder": key, "reason": issue_reason(key, mapping, payload, sent_keys)}
            for key in remaining
        ],
    }


def log_audit(label: str, audit: dict):
    print(
        "[slides_report]"
        f" {label}: template={audit.get('template_placeholder_count')} "
        f"mapping={audit.get('mapping_key_count')} "
        f"matched={audit.get('matched_count')} "
        f"missing={audit.get('missing_in_mapping_count')} "
        f"unused={audit.get('unused_mapping_key_count')} "
        f"remaining={audit.get('remaining_placeholder_count')}",
        flush=True,
    )
    for item in audit.get("missing_in_mapping", [])[:50]:
        print(f"[slides_report] missing {item['placeholder']}: {item['reason']}", flush=True)
    for item in audit.get("remaining_placeholders", [])[:50]:
        print(f"[slides_report] remaining {item['placeholder']}: {item['reason']}", flush=True)


class SlidesReportRepository:
    def __init__(self):
        self.engine = create_engine(database_url(), pool_pre_ping=True)

    def report_payload(self, client_id: str, period_id: str) -> dict:
        with self.engine.begin() as conn:
            client = row_dict(
                conn.execute(
                    text(
                        """
                        SELECT id, client_code, client_name, industry,
                               has_instagram, has_facebook, has_tiktok, has_youtube
                        FROM clients
                        WHERE id = :client_id
                        """
                    ),
                    {"client_id": client_id},
                ).mappings().first()
            )
            period = row_dict(
                conn.execute(
                    text(
                        """
                        SELECT id, period_label, period_start, period_end
                        FROM report_periods
                        WHERE id = :period_id AND client_id = :client_id
                        """
                    ),
                    {"client_id": client_id, "period_id": period_id},
                ).mappings().first()
            )
            if not client or not period:
                raise ValueError("Client or report period not found")

            own_profiles = [
                dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT platform, profile_name, profile_url, source_profile_id
                        FROM client_social_profiles
                        WHERE client_id = :client_id
                          AND is_active = TRUE
                        """
                    ),
                    {"client_id": client_id},
                ).mappings()
            ]
            self_terms = client_self_terms(client, own_profiles)

            reports = {}
            content = {}
            all_content = {}
            competitors = {}
            competitor_content = {}
            kpi_results = {}
            trends = {}
            for platform, table_name in PLATFORM_TABLES.items():
                if not client.get(f"has_{platform}"):
                    continue
                reports[platform] = row_dict(
                    conn.execute(
                        text(
                            f"""
                            SELECT r.*, p.profile_name, p.profile_url, p.image_url
                            FROM {table_name} r
                            LEFT JOIN client_social_profiles p ON p.id = r.profile_id
                            WHERE r.client_id = :client_id
                              AND r.report_period_id = :period_id
                            ORDER BY r.updated_at DESC
                            LIMIT 1
                            """
                        ),
                        {"client_id": client_id, "period_id": period_id},
                    ).mappings().first()
                )
                content[platform] = self.content_posts(conn, client_id, period_id, platform)
                all_content[platform] = self.all_content_posts(
                    conn,
                    client_id,
                    period_id,
                    platform,
                )
                competitor_content[platform] = self.competitor_content_posts(
                    conn,
                    client_id,
                    period_id,
                    platform,
                    self_terms,
                )
                competitor_rows = [
                    dict(row)
                    for row in conn.execute(
                        text(
                            """
                            SELECT profile_name, total_followers, follower_growth,
                                   follower_growth_rate, total_posts, total_engagement,
                                   engagement_rate, reach, impressions, profile_url, image_url
                            FROM competitor_profile_reports
                            WHERE client_id = :client_id
                              AND report_period_id = :period_id
                              AND platform = :platform
                            ORDER BY total_engagement DESC NULLS LAST,
                                     total_followers DESC NULLS LAST
                            LIMIT 20
                            """
                        ),
                        {
                            "client_id": client_id,
                            "period_id": period_id,
                            "platform": platform,
                        },
                    ).mappings()
                ]
                competitors[platform] = [
                    row for row in competitor_rows if not is_self_profile(row, self_terms)
                ][:5]
                kpi_results[platform] = [
                    dict(row)
                    for row in conn.execute(
                        text(
                            """
                            SELECT metric_name, actual_month, actual_year, target_month,
                                   target_year, achievement_month, achievement_year, unit
                            FROM kpi_results
                            WHERE client_id = :client_id
                              AND report_period_id = :period_id
                              AND platform = :platform
                            ORDER BY metric_name
                            """
                        ),
                        {
                            "client_id": client_id,
                            "period_id": period_id,
                            "platform": platform,
                        },
                    ).mappings()
                ]
                trends[platform] = self.monthly_trends(conn, client_id, period, platform, table_name)

            insights = [
                dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT platform, section_key, insight_key, insight_text,
                               display_order, source, metadata
                        FROM report_insights
                        WHERE client_id = :client_id
                          AND report_period_id = :period_id
                        ORDER BY platform NULLS FIRST, display_order NULLS LAST,
                                 section_key, insight_key
                        """
                    ),
                    {"client_id": client_id, "period_id": period_id},
                ).mappings()
            ]

            return {
                "client": client,
                "period": period,
                "reports": reports,
                "content": content,
                "all_content": all_content,
                "competitors": competitors,
                "competitor_content": competitor_content,
                "kpi_results": kpi_results,
                "trends": trends,
                "insights": insights,
            }

    def content_posts(self, conn, client_id: str, period_id: str, platform: str) -> dict:
        rows = conn.execute(
            text(
                """
                SELECT
                    post_id, published_at, caption, permalink, image_url,
                    content_type, content_rank, performance_bucket,
                    likes, comments, shares, saves, reposts, reactions,
                    views, reach, total_engagement, engagement_rate
                FROM social_content_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND platform = :platform
                  AND performance_bucket IN ('top', 'low')
                ORDER BY
                    CASE WHEN performance_bucket = 'top' THEN 0 ELSE 1 END,
                    content_rank ASC NULLS LAST,
                    total_engagement DESC NULLS LAST
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
            },
        ).mappings()
        candidates = {"top": [], "low": []}
        for row in rows:
            item = dict(row)
            bucket = item.pop("performance_bucket")
            candidates.setdefault(bucket, []).append(item)

        top_posts = candidates["top"][:3]
        top_identities = {content_identity(post) for post in top_posts}
        low_posts = [
            post
            for post in candidates["low"]
            if content_identity(post) not in top_identities
        ][:3]
        return {"top": top_posts, "low": low_posts}

    def all_content_posts(
        self,
        conn,
        client_id: str,
        period_id: str,
        platform: str,
    ) -> list[dict]:
        rows = conn.execute(
            text(
                """
                SELECT
                    post_id, published_at, caption, permalink, image_url,
                    content_type, likes, comments, shares, saves, reposts,
                    reactions, views, reach, total_engagement, engagement_rate
                FROM social_content_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND platform = :platform
                  AND performance_bucket = 'all'
                ORDER BY published_at ASC NULLS LAST, created_at ASC
                LIMIT 24
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
            },
        ).mappings()
        return [dict(row) for row in rows]

    def competitor_content_posts(
        self,
        conn,
        client_id: str,
        period_id: str,
        platform: str,
        self_terms: dict | None = None,
    ) -> list[dict]:
        rows = conn.execute(
            text(
                """
                SELECT
                    profile_name, post_id, published_at, caption, permalink, image_url,
                    content_type, content_rank, performance_bucket,
                    likes, comments, shares, saves, reposts, reactions,
                    views, reach, total_engagement, engagement_rate
                FROM competitor_content_reports
                WHERE client_id = :client_id
                  AND report_period_id = :period_id
                  AND platform = :platform
                  AND performance_bucket = 'best_competitor'
                ORDER BY
                    total_engagement DESC NULLS LAST,
                    content_rank ASC NULLS LAST
                LIMIT 20
                """
            ),
            {
                "client_id": client_id,
                "period_id": period_id,
                "platform": platform,
            },
        ).mappings()
        filtered = [
            dict(row)
            for row in rows
            if not is_self_profile(dict(row), self_terms or {"long": set(), "short": set()})
        ]
        return filtered[:3]

    def monthly_trends(self, conn, client_id: str, period: dict, platform: str, table_name: str) -> list[dict]:
        follower_field = "total_subscribers" if platform == "youtube" else "total_followers"
        growth_field = "subscriber_growth" if platform == "youtube" else "follower_growth"
        growth_rate_field = "subscriber_growth_rate" if platform == "youtube" else "follower_growth_rate"
        gained_field = "subscriber_growth" if platform == "youtube" else "follows"
        lost_field = "subscribers_lost" if platform == "youtube" else "unfollows"
        reach_field = "COALESCE(r.reach, r.total_views)" if platform in {"tiktok", "youtube"} else "COALESCE(r.reach, r.impressions)"
        impressions_field = "r.total_views" if platform in {"tiktok", "youtube"} else "r.impressions"
        rows = conn.execute(
            text(
                f"""
                WITH periods AS (
                    SELECT id, period_label, period_start
                    FROM report_periods
                    WHERE client_id = :client_id
                      AND period_start <= :period_start
                    ORDER BY period_start DESC
                    LIMIT 6
                ),
                ranked_reports AS (
                    SELECT
                        r.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY r.report_period_id
                            ORDER BY
                                (r.profile_id IS NOT NULL) DESC,
                                r.updated_at DESC,
                                r.created_at DESC
                        ) AS report_rank
                    FROM {table_name} r
                    JOIN periods p ON p.id = r.report_period_id
                    WHERE r.client_id = :client_id
                )
                SELECT
                    p.period_label,
                    p.period_start,
                    r.{follower_field} AS audience_total,
                    r.{growth_field} AS growth,
                    r.{growth_rate_field} AS growth_rate,
                    r.{gained_field} AS audience_gained,
                    r.{lost_field} AS audience_lost,
                    r.total_engagement,
                    r.engagement_rate,
                    {reach_field} AS reach_or_views,
                    {impressions_field} AS impressions_or_views,
                    r.likes,
                    r.comments,
                    r.shares,
                    r.total_posts
                FROM periods p
                LEFT JOIN ranked_reports r
                    ON r.report_period_id = p.id
                   AND r.report_rank = 1
                ORDER BY p.period_start DESC
                """
            ),
            {
                "client_id": client_id,
                "period_start": period["period_start"],
            },
        ).mappings()
        return [dict(row) for row in rows]


def report_value(report: dict | None, platform: str, field: str):
    if not report:
        return None
    if field == "audience_total":
        return report.get("total_subscribers") if platform == "youtube" else report.get("total_followers")
    if field == "growth":
        return report.get("subscriber_growth") if platform == "youtube" else report.get("follower_growth")
    if field == "growth_rate":
        return report.get("subscriber_growth_rate") if platform == "youtube" else report.get("follower_growth_rate")
    if field == "audience_gained":
        return report.get("subscribers_gained") or report.get("follows")
    if field == "audience_lost":
        return report.get("subscribers_lost") if platform == "youtube" else report.get("unfollows")
    if field == "views":
        return report.get("total_views") or report.get("impressions")
    return report.get(field)


def kpi_by_metric(rows: list[dict]) -> dict:
    return {str(row.get("metric_name") or "").lower(): row for row in rows}


def demographic_summary(report: dict | None) -> str:
    demographics = (report or {}).get("demographics") or {}
    if not demographics:
        return "-"
    if isinstance(demographics, str):
        try:
            demographics = json.loads(demographics)
        except json.JSONDecodeError:
            return clean_text(demographics, 120)
    if not isinstance(demographics, dict) or not demographics:
        return "-"
    parts = []
    for key, value in list(demographics.items())[:3]:
        label = str(key).replace("_", " ").title()
        parts.append(f"{label}: {fmt_percent(value) if isinstance(value, (int, float)) else value}")
    return "; ".join(parts) if parts else "-"


def add_kpi_mapping(mapping: dict, prefix: str, platform: str, rows: list[dict], report: dict | None):
    kpis = kpi_by_metric(rows)
    metric_aliases = {
        "followers": ["FOL"],
        "subscribers": ["SUB"],
        "reach": ["REACH"],
        "views": ["VIEWS"],
        "engagement": ["ENG", "INT"],
        "likes": ["LIKES"],
    }
    fallback_actuals = {
        "followers": report_value(report, platform, "audience_total"),
        "subscribers": report_value(report, platform, "audience_total"),
        "reach": report_value(report, platform, "reach"),
        "views": report_value(report, platform, "views"),
        "engagement": report_value(report, platform, "total_engagement"),
        "likes": report_value(report, platform, "likes"),
    }
    for metric_name, aliases in metric_aliases.items():
        row = kpis.get(metric_name) or {}
        actual_month = row.get("actual_month", fallback_actuals.get(metric_name))
        actual_year = row.get("actual_year", actual_month)
        for period_name, actual in (("MONTH", actual_month), ("YEAR", actual_year)):
            target = row.get(f"target_{period_name.lower()}")
            achievement = row.get(f"achievement_{period_name.lower()}")
            for alias in aliases:
                mapping[placeholder(f"{prefix}_{alias}_TARGET_{period_name}")] = fmt_number(target)
                mapping[placeholder(f"{prefix}_{alias}_ACTUAL_{period_name}")] = fmt_number(actual)
                mapping[placeholder(f"{prefix}_{alias}_PCT_{period_name}")] = (
                    fmt_percent(achievement) if achievement is not None else pct(actual, target)
                )


def add_platform_mapping(mapping: dict, payload: dict, platform: str):
    prefix = PLATFORM_PREFIXES[platform]
    report = payload["reports"].get(platform)
    content = payload["content"].get(platform, {})
    all_content = payload.get("all_content", {}).get(platform, [])
    competitors = payload["competitors"].get(platform, [])
    competitor_content = payload.get("competitor_content", {}).get(platform, [])
    trends = payload["trends"].get(platform, [])
    label = PLATFORM_LABELS[platform]

    audience_label = "Subscribers" if platform == "youtube" else "Followers"
    audience_total = report_value(report, platform, "audience_total")
    growth = report_value(report, platform, "growth")
    growth_display = growth if growth is not None else audience_total
    growth_rate = report_value(report, platform, "growth_rate")
    gained = report_value(report, platform, "audience_gained")
    lost = report_value(report, platform, "audience_lost")
    reach = report_value(report, platform, "reach")
    views = report_value(report, platform, "views")
    interactions = report_value(report, platform, "total_engagement")
    er = report_value(report, platform, "engagement_rate")

    mapping.update(
        {
            placeholder(f"{prefix}_TOTAL_FOLLOWERS"): fmt_number(audience_total),
            placeholder(f"{prefix}_TOTAL_SUBSCRIBERS"): fmt_number(audience_total),
            placeholder(f"{prefix}_TOTAL_FOL"): fmt_number(audience_total),
            placeholder(f"{prefix}_TOTAL_SUB"): fmt_number(audience_total),
            placeholder(f"{prefix}_FOLLOWERS_GROWTH"): fmt_number(growth_display),
            placeholder(f"{prefix}_SUBSCRIBER_GROWTH"): fmt_number(growth_display),
            placeholder(f"{prefix}_FOLLOWERS_GROWTH_RATE"): fmt_percent(growth_rate),
            placeholder(f"{prefix}_SUBSCRIBER_GROWTH_RATE"): fmt_percent(growth_rate),
            placeholder(f"{prefix}_FOLLOWS"): fmt_number(gained),
            placeholder(f"{prefix}_SUBSCRIBERS_GAINED"): fmt_number(gained),
            placeholder(f"{prefix}_UNFOLLOWS"): fmt_number(lost),
            placeholder(f"{prefix}_SUBSCRIBERS_LOST"): fmt_number(lost),
            placeholder(f"{prefix}_TOTAL_REACH"): fmt_number(reach),
            placeholder(f"{prefix}_REACH"): fmt_number(reach),
            placeholder(f"{prefix}_TOTAL_VIEWS"): fmt_number(views),
            placeholder(f"{prefix}_TOTAL_INTERACTIONS"): fmt_number(interactions),
            placeholder(f"{prefix}_TOTAL_INT"): fmt_number(interactions),
            placeholder(f"{prefix}_TOTAL_ENGAGEMENT"): fmt_number(interactions),
            placeholder(f"{prefix}_TOTAL_ENG"): fmt_number(interactions),
            placeholder(f"{prefix}_ENGAGEMENT"): fmt_number(interactions),
            placeholder(f"{prefix}_ENG"): fmt_number(interactions),
            placeholder(f"{prefix}_TOTAL_LIKES"): fmt_number(report_value(report, platform, "likes")),
            placeholder(f"{prefix}_LIKES"): fmt_number(report_value(report, platform, "likes")),
            placeholder(f"{prefix}_TOTAL_COMMENTS"): fmt_number(report_value(report, platform, "comments")),
            placeholder(f"{prefix}_COMMENT"): fmt_number(report_value(report, platform, "comments")),
            placeholder(f"{prefix}_COMMENTS"): fmt_number(report_value(report, platform, "comments")),
            placeholder(f"{prefix}_TOTAL_SHARES"): fmt_number(report_value(report, platform, "shares")),
            placeholder(f"{prefix}_SHARE"): fmt_number(report_value(report, platform, "shares")),
            placeholder(f"{prefix}_SHARES"): fmt_number(report_value(report, platform, "shares")),
            placeholder(f"{prefix}_TOTAL_SAVED"): fmt_number(report_value(report, platform, "saves")),
            placeholder(f"{prefix}_TOTAL_SAVES"): fmt_number(report_value(report, platform, "saves")),
            placeholder(f"{prefix}_TOTAL_REPOSTS"): fmt_number(report_value(report, platform, "reposts")),
            placeholder(f"{prefix}_AVG_ENGAGEMENT_RATE"): fmt_percent(er),
            placeholder(f"{prefix}_AVG_ER"): fmt_percent(er),
            placeholder(f"{prefix}_ER"): fmt_percent(er),
            placeholder(f"{prefix}_TOTAL_POSTS"): fmt_number(report_value(report, platform, "total_posts")),
            placeholder(f"{prefix}_TOTAL_REELS"): fmt_number(report_value(report, platform, "reels_posts")),
            placeholder(f"{prefix}_TOTAL_CAROUSEL"): fmt_number(report_value(report, platform, "carousel_posts")),
            placeholder(f"{prefix}_TOTAL_SINGLE"): fmt_number(report_value(report, platform, "single_posts")),
            placeholder(f"{prefix}_TOTAL_STORIES"): fmt_number(report_value(report, platform, "story_posts")),
            placeholder(f"{prefix}_TOTAL_VIDEOS"): fmt_number(report_value(report, platform, "video_posts")),
            placeholder(f"{prefix}_TOTAL_SHORTS"): fmt_number(report_value(report, platform, "shorts_posts")),
            placeholder(f"{prefix}_TOTAL_LONG_FORM"): fmt_number(report_value(report, platform, "long_form_posts")),
            placeholder(f"{prefix}_TOTAL_LIVE"): fmt_number(report_value(report, platform, "live_posts")),
            placeholder(f"{prefix}_AUDIENCE_DEMOGRAPHIC"): demographic_summary(report),
            placeholder(f"{prefix}_PERFORMANCE_INSIGHT"): (
                f"{label} mencatat {fmt_number(audience_total)} {audience_label.lower()}, "
                f"{fmt_number(interactions)} total engagements, dan ER {fmt_percent(er)}."
            ),
            placeholder(f"{prefix}_FOLLOWERS_GROWTH_TEXT"): (
                f"{audience_label} berada di {fmt_number(audience_total)} pada periode ini."
            ),
            placeholder(f"{prefix}_INSIGHT_FOLLOWERS_GROWTH_TEXT"): (
                f"{audience_label} berada di {fmt_number(audience_total)} pada periode ini."
            ),
            placeholder(f"{prefix}_SUBSCRIBER_GROWTH_TEXT"): (
                f"Subscribers berada di {fmt_number(audience_total)} pada periode ini."
            ),
            placeholder(f"{prefix}_ENGAGEMENT_TREND_TEXT"): (
                f"Total engagement {label} periode ini mencapai {fmt_number(interactions)}."
            ),
            placeholder(f"{prefix}_BENCHMARK_NOTE"): "Benchmark dapat diperbarui setelah data kompetitor lengkap tersedia.",
            placeholder(f"{prefix}_TOP_CONTENT_SUCCESS_DRIVER"): "Top content dipilih berdasarkan total engagement tertinggi.",
            placeholder(f"{prefix}_LOW_CONTENT_FAILURE_DRIVER"): "Low content dipilih berdasarkan total engagement terendah.",
            placeholder(f"{prefix}_COMPETITOR_STRATEGY_INSIGHT"): "Competitor summary diambil dari data Fanpage Karma yang tersedia.",
        }
    )

    add_kpi_mapping(mapping, prefix, platform, payload["kpi_results"].get(platform, []), report)
    add_monthly_trends(mapping, prefix, platform, trends)
    add_competitors(mapping, prefix, competitors)
    add_competitor_content(mapping, prefix, competitor_content)
    add_posts(mapping, platform, prefix, "POST_TOP", content.get("top", []))
    add_posts(mapping, platform, prefix, "POST_LOW", content.get("low", []))
    add_evidence_posts(mapping, prefix, all_content)

    if platform == "instagram":
        add_legacy_instagram_aliases(mapping)


def add_monthly_trends(mapping: dict, prefix: str, platform: str, trends: list[dict]):
    padded = trends + [{} for _ in range(6)]
    for index, row in enumerate(padded[:6], start=1):
        month_label = "-"
        if row.get("period_start"):
            month_label = row["period_start"].strftime("%b")
        elif row.get("period_label"):
            month_label = clean_text(row.get("period_label"), 12)
        values = {
            "TOTAL_FOLLOWERS": fmt_number(row.get("audience_total")),
            "TOTAL_SUBSCRIBERS": fmt_number(row.get("audience_total")),
            "FOLLOWS": fmt_number(row.get("audience_gained")),
            "SUBSCRIBERS_GAINED": fmt_number(row.get("audience_gained")),
            "UNFOLLOWS": fmt_number(row.get("audience_lost")),
            "SUBSCRIBERS_LOST": fmt_number(row.get("audience_lost")),
            "NET_GROWTH": fmt_number(row.get("growth")),
            "GROWTH_RATE": fmt_percent(row.get("growth_rate")),
            "REACH": fmt_number(row.get("reach_or_views")),
            "VIEWS": fmt_number(row.get("reach_or_views")),
            "IMPR": fmt_number(row.get("impressions_or_views")),
            "ENGAGEMENT": fmt_number(row.get("total_engagement")),
            "ENG": fmt_number(row.get("total_engagement")),
            "ER": fmt_percent(row.get("engagement_rate")),
            "LIKES": fmt_number(row.get("likes")),
            "COMM": fmt_number(row.get("comments")),
            "COMMENTS": fmt_number(row.get("comments")),
            "SHARE": fmt_number(row.get("shares")),
            "SHARES": fmt_number(row.get("shares")),
            "POSTS": fmt_number(row.get("total_posts")),
        }
        mapping[placeholder(f"M{index}_NAME")] = month_label
        mapping[placeholder(f"M{index}_POSTS")] = values["POSTS"]
        for suffix, value in values.items():
            mapping[placeholder(f"M{index}_{prefix}_{suffix}")] = value
            mapping[placeholder(f"{prefix}_M{index}_{suffix}")] = value
            mapping[placeholder(f"{prefix}_{index}_{suffix}")] = value


def add_competitors(mapping: dict, prefix: str, competitors: list[dict]):
    padded = competitors + [{} for _ in range(5)]
    mapping[placeholder(f"{prefix}_COMP_SELF_GROWTH")] = "-"
    if competitors:
        self_row = competitors[0]
        mapping[placeholder(f"{prefix}_COMP_SELF_GROWTH")] = fmt_percent(self_row.get("follower_growth_rate"))
    for index, row in enumerate(padded[:5], start=1):
        base = f"{prefix}_COMP_{index}"
        mapping[placeholder(f"{base}_NAME")] = clean_text(row.get("profile_name"), 32)
        mapping[placeholder(f"{base}_FOL")] = fmt_number(row.get("total_followers"))
        mapping[placeholder(f"{base}_SUB")] = fmt_number(row.get("total_followers"))
        mapping[placeholder(f"{base}_GROWTH")] = fmt_percent(row.get("follower_growth_rate"))
        mapping[placeholder(f"{base}_POSTS")] = fmt_number(row.get("total_posts"))
        mapping[placeholder(f"{base}_ER")] = fmt_percent(row.get("engagement_rate"))
        mapping[placeholder(f"{base}_INT")] = fmt_number(row.get("total_engagement"))
        mapping[placeholder(f"{base}_ENG")] = fmt_number(row.get("total_engagement"))
        mapping[placeholder(f"{base}_ENGAGEMENT")] = fmt_number(row.get("total_engagement"))


def add_competitor_content(mapping: dict, prefix: str, posts: list[dict]):
    padded = posts + [{} for _ in range(3)]
    for index, post in enumerate(padded[:3], start=1):
        base = f"{prefix}_COMP_CT_{index}"
        legacy_base = f"COMP_CT_{index}"
        values = {
            "TITLE": clean_text(post.get("caption"), 80),
            "IMAGE": clean_text(post.get("image_url")),
            "TYPE": clean_text(post.get("content_type"), 24),
            "PROFILE": clean_text(post.get("profile_name"), 32),
            "VIEW": fmt_number(post.get("views") or post.get("reach")),
            "VIEWS": fmt_number(post.get("views") or post.get("reach")),
            "REACH": fmt_number(post.get("reach")),
            "LIKES": fmt_number(post.get("likes")),
            "COMMENT": fmt_number(post.get("comments")),
            "COMMENTS": fmt_number(post.get("comments")),
            "SHARE": fmt_number(post.get("shares")),
            "SHARES": fmt_number(post.get("shares")),
            "SAVE": fmt_number(post.get("saves")),
            "SAVES": fmt_number(post.get("saves")),
            "REPOST": fmt_number(post.get("reposts")),
            "REPOSTS": fmt_number(post.get("reposts")),
            "ER": fmt_percent(post.get("engagement_rate")),
            "INT": fmt_number(post.get("total_engagement")),
            "ENG": fmt_number(post.get("total_engagement")),
            "ENGAGEMENT": fmt_number(post.get("total_engagement")),
            "TOTAL_ENGAGEMENT": fmt_number(post.get("total_engagement")),
        }
        for suffix, value in values.items():
            mapping[placeholder(f"{base}_{suffix}")] = value
            if prefix == "IG":
                mapping[placeholder(f"{legacy_base}_{suffix}")] = value
        mapping[placeholder(f"{prefix}_POST_COMP_{index}_IMAGE")] = values["IMAGE"]


def add_posts(mapping: dict, platform: str, prefix: str, base_name: str, posts: list[dict]):
    padded = posts + [{} for _ in range(3)]
    prefixed_base = f"{prefix}_{base_name}"
    for index, post in enumerate(padded[:3], start=1):
        current_bases = [prefixed_base]
        if platform == "instagram":
            current_bases.append(base_name)
        for current_base in current_bases:
            key = f"{current_base}_{index}"
            mapping[placeholder(f"{key}_TITLE")] = clean_text(post.get("caption"), 80)
            mapping[placeholder(f"{key}_IMAGE")] = clean_text(post.get("image_url"))
            mapping[placeholder(f"{key}_TYPE")] = clean_text(post.get("content_type"), 24)
            mapping[placeholder(f"{key}_VIEW")] = fmt_number(post.get("views") or post.get("reach"))
            mapping[placeholder(f"{key}_VIEWS")] = fmt_number(post.get("views") or post.get("reach"))
            mapping[placeholder(f"{key}_REACH")] = fmt_number(post.get("reach"))
            mapping[placeholder(f"{key}_LIKES")] = fmt_number(post.get("likes"))
            mapping[placeholder(f"{key}_COMMENT")] = fmt_number(post.get("comments"))
            mapping[placeholder(f"{key}_COMMENTS")] = fmt_number(post.get("comments"))
            mapping[placeholder(f"{key}_SHARE")] = fmt_number(post.get("shares"))
            mapping[placeholder(f"{key}_SHARES")] = fmt_number(post.get("shares"))
            mapping[placeholder(f"{key}_SAVE")] = fmt_number(post.get("saves"))
            mapping[placeholder(f"{key}_SAVES")] = fmt_number(post.get("saves"))
            mapping[placeholder(f"{key}_REPOST")] = fmt_number(post.get("reposts"))
            mapping[placeholder(f"{key}_REPOSTS")] = fmt_number(post.get("reposts"))
            mapping[placeholder(f"{key}_ER")] = fmt_percent(post.get("engagement_rate"))
            mapping[placeholder(f"{key}_ENGAGEMENT")] = fmt_number(post.get("total_engagement"))
            for suffix in ("MEN", "WOMEN", "1824", "2534", "3544", "4554", "5564", "COUNTRY"):
                mapping.setdefault(placeholder(f"{key}_{suffix}"), "-")

    if platform == "instagram" and base_name == "POST_TOP":
        for index in range(1, 4):
            for suffix in (
                "TITLE", "IMAGE", "TYPE", "VIEW", "VIEWS", "REACH", "LIKES",
                "COMMENT", "COMMENTS", "SHARE", "SHARES", "SAVE", "SAVES",
                "REPOST", "REPOSTS", "ER", "ENGAGEMENT", "MEN", "WOMEN",
                "1824", "2534", "3544", "4554", "5564", "COUNTRY",
            ):
                mapping[placeholder(f"POST_{index}_{suffix}")] = mapping.get(
                    placeholder(f"POST_TOP_{index}_{suffix}"),
                    "-",
                )


def add_evidence_posts(mapping: dict, prefix: str, posts: list[dict]):
    padded = posts + [{} for _ in range(24)]
    for index, post in enumerate(padded[:24], start=1):
        base = f"{prefix}_EVIDENCE_{index}"
        published_at = post.get("published_at")
        if hasattr(published_at, "strftime"):
            published_at = published_at.strftime("%d %B %Y").upper()
        mapping[placeholder(f"{base}_DATE")] = clean_text(published_at, 28)
        mapping[placeholder(f"{base}_CATEGORY")] = clean_text(
            post.get("content_type"),
            24,
        )
        mapping[placeholder(f"{base}_TITLE")] = clean_text(post.get("caption"), 72)
        mapping[placeholder(f"{base}_IMAGE")] = clean_text(post.get("image_url"))
        mapping[placeholder(f"{base}_ER")] = fmt_percent(post.get("engagement_rate"))
        mapping[placeholder(f"{base}_ENGAGEMENT")] = fmt_number(
            post.get("total_engagement")
        )
        mapping[placeholder(f"{base}_VIEWS")] = fmt_number(
            post.get("views") or post.get("reach")
        )


def add_legacy_instagram_aliases(mapping: dict):
    alias_pairs = {
        "COMP_SELF_GROWTH": "IG_COMP_SELF_GROWTH",
        "IG_TOTAL_SAVED": "IG_TOTAL_SAVES",
        "INSIGT_FOLLOWERS_GROWTH_TEXT": "IG_FOLLOWERS_GROWTH_TEXT",
        "ENGAGEMENT_TREND_TEXT": "IG_ENGAGEMENT_TREND_TEXT",
        "BENCHMARK_NOTE": "IG_BENCHMARK_NOTE",
        "TOP_CONTENT_SUCCESS_DRIVER": "IG_TOP_CONTENT_SUCCESS_DRIVER",
        "LOW_CONTENT_FAILURE_DRIVER": "IG_LOW_CONTENT_FAILURE_DRIVER",
        "COMPETITOR_STRATEGY_INSIGHT": "IG_COMPETITOR_STRATEGY_INSIGHT",
    }
    for target, source in alias_pairs.items():
        mapping[placeholder(target)] = mapping.get(placeholder(source), "-")
    for index in range(1, 6):
        for suffix in ("NAME", "FOL", "GROWTH", "POSTS", "ER", "INT", "ENG", "ENGAGEMENT"):
            mapping[placeholder(f"COMP_{index}_{suffix}")] = mapping.get(
                placeholder(f"IG_COMP_{index}_{suffix}"),
                "-",
            )


def empty_defaults() -> dict:
    mapping = {}
    common_keys = [
        "EXECUTIVE_SUMMARY",
        "NEXT_REPORT_PERIOD",
        "DEMOGRAPHICS_INSIGHT",
        "AGE_18_24_PCT",
        "AGE_25_34_PCT",
        "AGE_35_44_PCT",
        "AGE_45_PLUS_PCT",
        "GENDER_MALE_PCT",
        "GENDER_FEMALE_PCT",
        "TOP_CITY_1",
        "TOP_CITY_1_PCT",
        "TOP_CITY_2",
        "TOP_CITY_2_PCT",
        "TOP_CITY_3",
        "TOP_CITY_3_PCT",
        "WEB_PREV_SESSIONS",
        "WEB_CURR_SESSIONS",
        "WEB_PREV_ORGANIC",
        "WEB_CURR_ORGANIC",
        "WEB_PREV_BOUNCE",
        "WEB_CURR_BOUNCE",
        "WEB_PREV_DUR",
        "WEB_CURR_DUR",
        "SSL_EXPIRY_DATE",
        "DOMAIN_REMAINING_DAYS",
        "WEB_SEO_RECO_TEXT",
        "ADS_REACH_TARGET",
        "ADS_REACH_ACTUAL",
        "ADS_REACH_PCT",
        "ADS_REACH_SPENT",
        "ADS_REACH_REM",
        "ADS_INT_TARGET",
        "ADS_INT_ACTUAL",
        "ADS_INT_PCT",
        "ADS_INT_SPENT",
        "ADS_INT_REM",
        "ADS_YT_TARGET",
        "ADS_YT_ACTUAL",
        "ADS_YT_PCT",
        "ADS_YT_SPENT",
        "ADS_YT_REM",
        "ADS_TK_TARGET",
        "ADS_TK_ACTUAL",
        "ADS_TK_PCT",
        "ADS_TK_SPENT",
        "ADS_TK_REM",
        "ADS_TOTAL_SPENT",
        "ADS_TOTAL_REM",
        "ADS_AVG_CPM",
        "ADS_AVG_CPC",
        "ADS_AVG_CTR",
        "SUMMARY_POINT_1",
        "SUMMARY_POINT_2",
        "SUMMARY_POINT_3",
        "SUMMARY_POINT_4",
        "RECOMMENDATION_1",
        "RECOMMENDATION_2",
        "RECOMMENDATION_3",
    ]
    insight_suffixes = [
        "SUMMARY_POINT_1",
        "SUMMARY_POINT_2",
        "SUMMARY_POINT_3",
        "SUMMARY_POINT_4",
        "RECOMMENDATION_1",
        "RECOMMENDATION_2",
        "RECOMMENDATION_3",
        "REACH_INSIGHT_SUMMARY",
    ]
    for key in common_keys:
        mapping[placeholder(key)] = "-"
    for prefix in PLATFORM_PREFIXES.values():
        for suffix in insight_suffixes:
            mapping[placeholder(f"{prefix}_{suffix}")] = "-"
    return mapping


def build_mapping(payload: dict) -> dict:
    client = payload["client"]
    period = payload["period"]
    report_period = period.get("period_label") or period["period_start"].strftime("%B %Y")
    mapping = empty_defaults()
    mapping.update(
        {
            "{{CLIENT_NAME}}": client["client_name"],
            "{{AGENCY_NAME}}": os.getenv("REPORT_AGENCY_NAME", "MAI"),
            "{{REPORT_PERIOD}}": report_period,
            "{{EXECUTIVE_SUMMARY}}": (
                f"Report {report_period} untuk {client['client_name']} dibuat dari data "
                "social media yang tersedia di dashboard."
            ),
            "{{SUMMARY_POINT_1}}": "Social media performance dihitung dari data report yang sudah diimport.",
            "{{SUMMARY_POINT_2}}": "KPI target dan achievement mengikuti input target di dashboard.",
            "{{SUMMARY_POINT_3}}": "Top dan low content dipilih berdasarkan total engagement.",
            "{{SUMMARY_POINT_4}}": "Field yang belum tersedia ditampilkan sebagai '-' sampai data lengkap diimport.",
            "{{RECOMMENDATION_1}}": "Lengkapi data yang masih kosong sebelum report final dikirim.",
            "{{RECOMMENDATION_2}}": "Gunakan top content sebagai referensi konten periode berikutnya.",
            "{{RECOMMENDATION_3}}": "Perbarui KPI target tahunan dan bulanan secara berkala.",
        }
    )

    totals = {"reach": 0, "views": 0, "interactions": 0, "posts": 0}
    er_values = []
    for platform in PLATFORM_TABLES:
        add_platform_mapping(mapping, payload, platform)
        report = payload["reports"].get(platform) or {}
        totals["reach"] += float(report.get("reach") or 0)
        totals["views"] += float(report.get("total_views") or report.get("impressions") or 0)
        totals["interactions"] += float(report.get("total_engagement") or 0)
        totals["posts"] += float(report.get("total_posts") or 0)
        if report.get("engagement_rate") is not None:
            er_values.append(float(report["engagement_rate"]))

    avg_er = sum(er_values) / len(er_values) if er_values else None
    mapping.update(
        {
            "{{TOTAL_REACH}}": fmt_number(totals["reach"]),
            "{{TOTAL_VIEWS}}": fmt_number(totals["views"]),
            "{{TOTAL_INTERACTIONS}}": fmt_number(totals["interactions"]),
            "{{TOTAL_ENGAGEMENT}}": fmt_number(totals["interactions"]),
            "{{TOTAL_ENG}}": fmt_number(totals["interactions"]),
            "{{TOTAL_POSTS}}": fmt_number(totals["posts"]),
            "{{AVG_ENGAGEMENT_RATE}}": fmt_percent(avg_er),
        }
    )
    apply_report_insights(mapping, payload.get("insights", []))
    return mapping


def apply_report_insights(mapping: dict, insight_rows: list[dict]) -> None:
    platform_targets = {
        "kpi_analysis": ("SUMMARY_POINT_1",),
        "socmed_overview_analysis": ("PERFORMANCE_INSIGHT", "SUMMARY_POINT_2"),
        "followers_growth_analysis": (
            "FOLLOWERS_GROWTH_TEXT",
            "INSIGHT_FOLLOWERS_GROWTH_TEXT",
            "SUBSCRIBER_GROWTH_TEXT",
            "SUMMARY_POINT_3",
        ),
        "growth_performance_analysis": (
            "ENGAGEMENT_TREND_TEXT",
            "REACH_INSIGHT_SUMMARY",
            "SUMMARY_POINT_4",
        ),
        "top_content_performance": ("TOP_CONTENT_SUCCESS_DRIVER",),
        "low_content_performance": ("LOW_CONTENT_FAILURE_DRIVER",),
        "competitor_analysis": (
            "COMPETITOR_STRATEGY_INSIGHT",
            "BENCHMARK_NOTE",
        ),
        "key_summary": ("KEY_SUMMARY", "KEY_SUMMARY_TEXT"),
    }

    for row in insight_rows:
        insight_text = str(row.get("insight_text") or "").strip()
        if not insight_text:
            continue

        platform = row.get("platform")
        insight_key = str(row.get("insight_key") or "")
        if platform is None and insight_key == "summary_result":
            mapping["{{EXECUTIVE_SUMMARY}}"] = insight_text
            continue

        prefix = PLATFORM_PREFIXES.get(str(platform))
        if not prefix:
            continue
        if insight_key == "action_plan":
            action_items = split_action_plan(insight_text)
            for index, action_item in enumerate(action_items, start=1):
                mapping[placeholder(f"{prefix}_RECOMMENDATION_{index}")] = action_item
            continue
        for suffix in platform_targets.get(insight_key, ()):
            mapping[placeholder(f"{prefix}_{suffix}")] = insight_text
            # The Instagram section of the template still contains legacy,
            # unprefixed insight placeholders alongside the newer IG_* names.
            if prefix == "IG" and suffix in {
                "FOLLOWERS_GROWTH_TEXT",
                "INSIGHT_FOLLOWERS_GROWTH_TEXT",
                "ENGAGEMENT_TREND_TEXT",
                "BENCHMARK_NOTE",
                "TOP_CONTENT_SUCCESS_DRIVER",
                "COMPETITOR_STRATEGY_INSIGHT",
            }:
                mapping[placeholder(suffix)] = insight_text


def split_action_plan(action_plan: str, limit: int = 3) -> list[str]:
    text = str(action_plan or "").strip()
    if not text:
        return []

    parts = re.split(r"\r?\n+|\s*;\s*", text)
    if len(parts) == 1:
        parts = re.split(r"(?<=[.!?])\s+", text)

    cleaned = []
    for part in parts:
        item = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", part).strip()
        if item:
            cleaned.append(item)
        if len(cleaned) == limit:
            break
    return cleaned or [text]


def share_presentation_as_editor(drive_service, presentation_id: str) -> dict:
    permission = (
        drive_service.permissions()
        .create(
            fileId=presentation_id,
            body={
                "type": "anyone",
                "role": "writer",
                "allowFileDiscovery": False,
            },
            fields="id,type,role",
            sendNotificationEmail=False,
        )
        .execute()
    )
    return permission


def replace_text_placeholders_chunked(
    slides_service,
    presentation_id: str,
    mapping: dict,
    chunk_size: int | None = None,
    skip_image_placeholders: bool | set[str] = False,
    allowed_placeholders: set[str] | None = None,
) -> dict:
    chunk_size = chunk_size or env_int("SLIDES_TEXT_BATCH_SIZE", 100)
    requests = []
    sent_keys = []
    occurrences_changed: dict[str, int] = {}
    skipped_image_placeholders = []
    skipped_non_template_placeholders = []
    skipped_image_keys = (
        skip_image_placeholders
        if isinstance(skip_image_placeholders, set)
        else None
    )
    for key, value in mapping.items():
        if allowed_placeholders is not None and key not in allowed_placeholders:
            skipped_non_template_placeholders.append(key)
            continue
        if is_image_placeholder_key(key):
            should_skip_image = (
                key in skipped_image_keys
                if skipped_image_keys is not None
                else bool(skip_image_placeholders)
            )
            if should_skip_image:
                skipped_image_placeholders.append(key)
                continue
            value = "-"
        sent_keys.append(key)
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {
                        "text": key,
                        "matchCase": True,
                    },
                    "replaceText": str(value),
                }
            }
        )

    batch_sizes = []
    for index in range(0, len(requests), chunk_size):
        batch = requests[index : index + chunk_size]
        batch_number = (index // chunk_size) + 1
        batch_sizes.append(len(batch))
        print(
            f"[slides_report] batchUpdate batch={batch_number} replaceTextRequests={len(batch)}",
            flush=True,
        )
        response = execute_slides_batch_update(slides_service, presentation_id, batch)
        replies = response.get("replies", [])
        batch_keys = sent_keys[index : index + chunk_size]
        for offset, key in enumerate(batch_keys):
            reply = replies[offset] if offset < len(replies) else {}
            occurrences_changed[key] = (
                reply.get("replaceAllText", {}).get("occurrencesChanged", 0)
            )
    print(
        f"[slides_report] batchUpdate totalPlaceholdersSent={len(sent_keys)} "
        f"totalRequests={len(requests)} totalBatches={len(batch_sizes)} "
        f"occurrencesChanged={sum(occurrences_changed.values())} "
        f"zeroMatches={sum(1 for value in occurrences_changed.values() if not value)} "
        f"skippedNonTemplate={len(skipped_non_template_placeholders)}",
        flush=True,
    )
    return {
        "sent_keys": sent_keys,
        "sent_key_count": len(sent_keys),
        "total_requests": len(requests),
        "batch_count": len(batch_sizes),
        "batch_sizes": batch_sizes,
        "skipped_image_placeholders": sorted(skipped_image_placeholders),
        "skipped_non_template_placeholders": sorted(skipped_non_template_placeholders),
        "occurrences_changed": occurrences_changed,
        "total_occurrences_changed": sum(occurrences_changed.values()),
    }


def should_replace_images() -> bool:
    return env_bool("SLIDES_REPLACE_IMAGES", False)


def fast_mode_enabled() -> bool:
    return env_bool("SLIDES_FAST_MODE", False)


def filter_to_template_enabled() -> bool:
    return env_bool("SLIDES_FILTER_TO_TEMPLATE", True)


def generate_dashboard_slides_report(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
    insight_overrides: list[dict] | None = None,
) -> dict:
    profiler = StepProfiler()
    load_dotenv(BASE_DIR / ".env")
    template_value = default_template()
    if not template_value:
        raise ValueError("SLIDES_TEMPLATE_ID is not configured.")
    template_id = extract_presentation_id(template_value)

    start = time.perf_counter()
    payload = SlidesReportRepository().report_payload(client_id, period_id)
    if insight_overrides:
        merged_insights = {
            (row.get("platform"), row.get("insight_key")): dict(row)
            for row in payload.get("insights", [])
        }
        for row in insight_overrides:
            key = (row.get("platform"), row.get("insight_key"))
            merged_insights[key] = dict(row)
        payload["insights"] = list(merged_insights.values())
    profiler.record("load_db_data", start)

    start = time.perf_counter()
    mapping = build_mapping(payload)
    profiler.record("build_mapping", start)

    credentials_path = resolve_project_path(default_credentials())
    if not credentials_path.exists():
        raise FileNotFoundError(f"Google credentials file not found: {credentials_path}")
    token_path = resolve_project_path(os.getenv("GOOGLE_TOKEN_FILE", "token.json"))
    oauth_port = int(os.getenv("GOOGLE_OAUTH_PORT", "0"))

    slides_service, drive_service = get_google_services(
        credentials_path,
        token_path,
        oauth_port,
    )

    result = {
        "template_id": template_id,
        "client_id": client_id,
        "period_id": period_id,
        "placeholder_count": len(mapping),
    }
    fast_mode = fast_mode_enabled()
    filter_to_template = filter_to_template_enabled()
    template_placeholders = set()
    replacement_placeholders = None
    if dry_run or not fast_mode or filter_to_template:
        start = time.perf_counter()
        template_placeholders = fetch_presentation_placeholders(slides_service, template_id)
        replacement_placeholders = template_placeholders if filter_to_template else None
        profiler.record(
            "template_scan" if dry_run or not fast_mode else "template_filter_scan",
            start,
        )
        preflight_audit = audit_mapping(template_placeholders, mapping, payload)
        result["audit"] = preflight_audit
        if dry_run or not fast_mode:
            log_audit("preflight", preflight_audit)
        else:
            print(
                "[slides_report] template_filter: "
                f"template={preflight_audit['template_placeholder_count']} "
                f"mapping={preflight_audit['mapping_key_count']} "
                f"matched={preflight_audit['matched_count']} "
                f"skipped={preflight_audit['unused_mapping_key_count']}",
                flush=True,
            )
    else:
        print("[slides] template_scan: skipped (fast mode)", flush=True)
        result["audit"] = {
            "template_placeholder_count": None,
            "mapping_key_count": len(mapping),
            "matched_count": None,
            "missing_in_mapping_count": None,
            "unused_mapping_key_count": None,
            "remaining_placeholder_count": None,
            "missing_in_mapping": [],
            "remaining_placeholders": [],
            "fallback_values": [],
        }
    if dry_run:
        result["mapping"] = mapping
        audit = result["audit"]
        result["debug_summary"] = {
            "total_template_placeholders": audit["template_placeholder_count"],
            "total_mapping_keys": audit["mapping_key_count"],
            "matched_placeholders": audit["matched_count"],
            "unmatched_template_placeholders": audit["missing_in_mapping_count"],
            "unused_mapping_keys": audit["unused_mapping_key_count"],
            "placeholder_masih_tersisa": [
                item["placeholder"]
                for item in audit["missing_in_mapping"]
            ],
        }
        profiler.total()
        result["profile"] = profiler.steps
        return result

    client_name = payload["client"]["client_name"]
    period_label = payload["period"].get("period_label") or payload["period"]["period_start"].strftime("%B %Y")
    report_name = f"SNS Report - {client_name} - {period_label} - {datetime.now():%Y%m%d-%H%M}"

    start = time.perf_counter()
    presentation_id = copy_template(drive_service, template_id, report_name)
    profiler.record("copy_template", start)

    start = time.perf_counter()
    permission = share_presentation_as_editor(drive_service, presentation_id)
    profiler.record("share_file", start)

    replace_images = should_replace_images()
    image_mapping = image_placeholder_mapping(mapping) if replace_images else {}
    image_keys_with_urls = set(image_mapping)

    # Text is the primary report output. Replace it before image work so an
    # inaccessible CDN image or a Slides image quota issue cannot leave the
    # report full of raw text placeholders.
    start = time.perf_counter()
    batch_audit = replace_text_placeholders_chunked(
        slides_service,
        presentation_id,
        mapping,
        skip_image_placeholders=image_keys_with_urls,
        allowed_placeholders=replacement_placeholders,
    )
    profiler.record("replace_text", start)

    start = time.perf_counter()
    structured_text_audit = replace_structured_text_placeholders(
        slides_service,
        presentation_id,
        mapping,
        skip_placeholders=image_keys_with_urls,
    )
    profiler.record("replace_structured_text", start)

    start = time.perf_counter()
    image_audit = {
        "attempted": 0,
        "replaced": [],
        "failed": [],
        "unmatched": [],
        "skipped_non_template": [],
    }
    if replace_images:
        if image_mapping:
            image_audit = replace_image_placeholders_safe(
                slides_service,
                presentation_id,
                image_mapping,
                allowed_placeholders=replacement_placeholders,
            )
    else:
        print("[slides] image_handling: image replacement disabled", flush=True)
    profiler.record("image_handling", start)

    # Image placeholders with inaccessible URLs may also exist as visible text
    # shapes. Replace those failures with the normal fallback after image work.
    replaced_image_keys = set(image_audit.get("replaced", []))
    failed_image_keys = image_keys_with_urls - replaced_image_keys
    if replacement_placeholders is not None:
        failed_image_keys &= replacement_placeholders
    image_fallback_audit = {
        "sent_keys": [],
        "sent_key_count": 0,
        "total_requests": 0,
        "batch_count": 0,
        "batch_sizes": [],
        "skipped_image_placeholders": [],
        "skipped_non_template_placeholders": [],
    }
    image_structured_fallback_audit = {
        "sent_keys": [],
        "sent_key_count": 0,
        "unique_key_count": 0,
        "batch_count": 0,
        "batch_sizes": [],
        "total_requests": 0,
    }
    if failed_image_keys:
        start = time.perf_counter()
        failed_image_mapping = {key: "-" for key in sorted(failed_image_keys)}
        image_fallback_audit = replace_text_placeholders_chunked(
            slides_service,
            presentation_id,
            failed_image_mapping,
            skip_image_placeholders=False,
            allowed_placeholders=replacement_placeholders,
        )
        profiler.record("replace_failed_image_text", start)

        start = time.perf_counter()
        image_structured_fallback_audit = replace_structured_text_placeholders(
            slides_service,
            presentation_id,
            failed_image_mapping,
        )
        profiler.record("replace_failed_image_structured_text", start)

    post_replace_audit = None
    if fast_mode:
        print("[slides] post_replace_scan: skipped (fast mode)", flush=True)
    else:
        start = time.perf_counter()
        remaining_placeholders = fetch_presentation_placeholders(slides_service, presentation_id)
        profiler.record("post_replace_scan", start)
        post_replace_audit = audit_mapping(
            template_placeholders,
            mapping,
            payload,
            sent_keys=(
                set(batch_audit["sent_keys"])
                | set(structured_text_audit["sent_keys"])
                | set(image_fallback_audit["sent_keys"])
                | set(image_structured_fallback_audit["sent_keys"])
                | replaced_image_keys
            ),
            remaining_placeholders=remaining_placeholders,
        )
        log_audit("post_replace", post_replace_audit)
    total_duration = profiler.total()

    result.update(
        {
            "presentation_id": presentation_id,
            "presentation_url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
            "report_name": report_name,
            "permission": permission,
            "images_replaced": bool(image_audit.get("replaced")),
            "image_replacement": image_audit,
            "batch_update": batch_audit,
            "structured_text_batch_update": structured_text_audit,
            "image_fallback_batch_update": image_fallback_audit,
            "image_structured_fallback_batch_update": image_structured_fallback_audit,
            "post_replace_audit": post_replace_audit,
            "fast_mode": fast_mode,
            "filter_to_template": bool(replacement_placeholders),
            "profile": profiler.steps,
            "total_duration_seconds": total_duration,
        }
    )
    return result
