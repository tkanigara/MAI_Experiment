from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import BinaryIO


META_ADS_FILE_TYPES = (
    "campaign",
    "adset",
    "ad",
    "placement",
    "demographic",
    "region",
)

FILE_LABELS = {
    "campaign": "Campaign",
    "adset": "Ad Set",
    "ad": "Ads",
    "placement": "Ads Placement",
    "demographic": "Ads Age/Gender",
    "region": "Ads Region",
}

# All source-specific names live here. The normalized records and persistence
# layer only use the canonical names on the right.
HEADER_ALIASES = {
    "awal pelaporan": "reporting_start",
    "reporting starts": "reporting_start",
    "reporting start": "reporting_start",
    "akhir pelaporan": "reporting_end",
    "reporting ends": "reporting_end",
    "reporting end": "reporting_end",
    "id kampanye": "campaign_external_id",
    "campaign id": "campaign_external_id",
    "nama kampanye": "campaign_name",
    "campaign name": "campaign_name",
    "id set iklan": "adset_external_id",
    "ad set id": "adset_external_id",
    "nama set iklan": "adset_name",
    "ad set name": "adset_name",
    "id iklan": "ad_external_id",
    "ad id": "ad_external_id",
    "nama iklan": "ad_name",
    "ad name": "ad_name",
    "penayangan kampanye": "delivery_status",
    "campaign delivery": "delivery_status",
    "penayangan set iklan": "delivery_status",
    "ad set delivery": "delivery_status",
    "penayangan iklan": "delivery_status",
    "ad delivery": "delivery_status",
    "hasil": "result_value",
    "results": "result_value",
    "indikator hasil": "result_type",
    "result indicator": "result_type",
    "biaya per hasil": "cost_per_result",
    "cost per result": "cost_per_result",
    "anggaran set iklan": "budget",
    "ad set budget": "budget",
    "jenis anggaran set iklan": "budget_type",
    "ad set budget type": "budget_type",
    "jumlah yang dibelanjakan (idr)": "spend",
    "amount spent (idr)": "spend",
    "amount spent": "spend",
    "impresi": "impressions",
    "impressions": "impressions",
    "jangkauan": "reach",
    "reach": "reach",
    "berakhir": "end_value",
    "ends": "end_value",
    "mulai": "start_date",
    "starts": "start_date",
    "pengaturan atribusi": "attribution_setting",
    "attribution setting": "attribution_setting",
    "tawaran": "bid",
    "bid": "bid",
    "jenis tawaran": "bid_type",
    "bid type": "bid_type",
    "editan signifikan terakhir": "last_significant_edit",
    "last significant edit": "last_significant_edit",
    "peringkat kualitas": "quality_ranking",
    "quality ranking": "quality_ranking",
    "peringkat nilai interaksi": "engagement_rate_ranking",
    "engagement rate ranking": "engagement_rate_ranking",
    "peringkat nilai konversi": "conversion_rate_ranking",
    "conversion rate ranking": "conversion_rate_ranking",
    "reaction/reach": "reaction_reach",
    "interaksi postingan": "post_engagements",
    "post engagements": "post_engagements",
    "klik tautan": "link_clicks",
    "link clicks": "link_clicks",
    "ctr (rasio klik tayang tautan)": "link_ctr",
    "ctr (link click-through rate)": "link_ctr",
    "frequency": "frequency",
    "frekuensi": "frequency",
    "pengikut instagram": "instagram_follows",
    "instagram follows": "instagram_follows",
    "interaksi halaman": "page_engagements",
    "page engagements": "page_engagements",
    "hasil (awal)": "initial_result_value",
    "results (initial)": "initial_result_value",
    "indikator hasil (awal)": "initial_result_type",
    "result indicator (initial)": "initial_result_type",
    "platform": "publisher_platform",
    "penempatan": "placement",
    "placement": "placement",
    "platform perangkat": "device_platform",
    "device platform": "device_platform",
    "usia": "age",
    "age": "age",
    "jenis kelamin": "gender",
    "gender": "gender",
    "wilayah": "region",
    "region": "region",
}

NUMERIC_FIELDS = {
    "result_value",
    "cost_per_result",
    "spend",
    "impressions",
    "reach",
    "bid",
    "reaction_reach",
    "post_engagements",
    "link_clicks",
    "link_ctr",
    "frequency",
    "instagram_follows",
    "page_engagements",
    "initial_result_value",
}

REQUIRED_FIELDS = {
    "campaign": {"reporting_start", "reporting_end", "campaign_name"},
    "adset": {"reporting_start", "reporting_end", "adset_name"},
    "ad": {"reporting_start", "reporting_end", "ad_name", "adset_name"},
    "placement": {
        "reporting_start",
        "reporting_end",
        "ad_name",
        "adset_name",
        "publisher_platform",
        "placement",
        "device_platform",
    },
    "demographic": {
        "reporting_start",
        "reporting_end",
        "ad_name",
        "adset_name",
        "age",
        "gender",
    },
    "region": {
        "reporting_start",
        "reporting_end",
        "ad_name",
        "adset_name",
        "region",
    },
}

ENTITY_FIELD = {
    "campaign": "campaign_name",
    "adset": "adset_name",
    "ad": "ad_name",
    "placement": "ad_name",
    "demographic": "ad_name",
    "region": "ad_name",
}

NULL_MARKERS = {"", "-", "—", "n/a", "na", "null", "none"}


class MetaAdsValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMetaAdsFile:
    file_type: str
    filename: str
    headers: tuple[str, ...]
    canonical_headers: tuple[str, ...]
    rows: tuple[dict, ...]
    summary_row: dict | None
    summary_raw_data: dict | None
    warnings: tuple[str, ...]

    @property
    def period(self) -> tuple[date, date]:
        first = self.rows[0] if self.rows else self.summary_row
        if not first:
            raise MetaAdsValidationError(f"{self.filename}: file has no usable rows.")
        return first["reporting_start"], first["reporting_end"]


def _normalized_header(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", str(value or "").lstrip("\ufeff"))
    return re.sub(r"\s+", " ", value.strip()).casefold()


def canonical_header(value: str | None) -> str | None:
    return HEADER_ALIASES.get(_normalized_header(value))


def _is_null(value) -> bool:
    return value is None or str(value).strip().casefold() in NULL_MARKERS


def _parse_decimal(value, *, filename: str, row_number: int, header: str) -> Decimal | None:
    if _is_null(value):
        return None
    text_value = str(value).strip().replace("%", "").replace("\u00a0", "").replace(" ", "")
    if "," in text_value and "." in text_value:
        if text_value.rfind(",") > text_value.rfind("."):
            text_value = text_value.replace(".", "").replace(",", ".")
        else:
            text_value = text_value.replace(",", "")
    elif "," in text_value:
        parts = text_value.split(",")
        if len(parts) == 2 and len(parts[1]) not in {3}:
            text_value = ".".join(parts)
        else:
            text_value = "".join(parts)
    try:
        return Decimal(text_value)
    except InvalidOperation as exc:
        raise MetaAdsValidationError(
            f"{filename}: row {row_number}, column '{header}' contains invalid numeric value {value!r}."
        ) from exc


def _parse_date(value, *, filename: str, row_number: int, header: str) -> date | None:
    if _is_null(value):
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise MetaAdsValidationError(
            f"{filename}: row {row_number}, column '{header}' must be an ISO date (YYYY-MM-DD)."
        ) from exc


def _parse_datetime(value, *, filename: str, row_number: int, header: str) -> datetime | None:
    if _is_null(value) or str(value).strip() == "0":
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise MetaAdsValidationError(
            f"{filename}: row {row_number}, column '{header}' contains an invalid timestamp."
        ) from exc


def _read_upload(file_item) -> tuple[str, bytes]:
    filename = str(getattr(file_item, "filename", "") or "meta-ads.csv")
    stream: BinaryIO = getattr(file_item, "file", file_item)
    if not hasattr(stream, "read"):
        raise MetaAdsValidationError(f"{filename}: uploaded file cannot be read.")
    try:
        stream.seek(0)
    except (AttributeError, OSError):
        pass
    raw = stream.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw:
        raise MetaAdsValidationError(f"{filename}: file is empty.")
    return filename, raw


def _decode_csv(filename: str, raw: bytes) -> tuple[list[str], list[dict]]:
    try:
        text_value = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MetaAdsValidationError(f"{filename}: file must be UTF-8 encoded.") from exc
    sample = text_value[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text_value), delimiter=delimiter)
    headers = [str(header or "").strip().lstrip("\ufeff") for header in (reader.fieldnames or [])]
    if not headers or any(not header for header in headers):
        raise MetaAdsValidationError(f"{filename}: CSV header is missing or malformed.")
    if len(set(headers)) != len(headers):
        raise MetaAdsValidationError(f"{filename}: CSV contains duplicate headers.")
    rows = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise MetaAdsValidationError(
                f"{filename}: row {row_number} has more values than the header."
            )
        rows.append({header: str(row.get(header) or "").strip() for header in headers})
    if not rows:
        raise MetaAdsValidationError(f"{filename}: file has no data rows.")
    return headers, rows


def detect_file_type(headers: list[str] | tuple[str, ...]) -> str:
    canonical = {canonical_header(header) for header in headers}
    if "campaign_name" in canonical:
        return "campaign"
    if "age" in canonical or "gender" in canonical:
        return "demographic"
    if "region" in canonical:
        return "region"
    if "publisher_platform" in canonical or "placement" in canonical:
        return "placement"
    if "ad_name" in canonical:
        return "ad"
    if "adset_name" in canonical:
        return "adset"
    raise MetaAdsValidationError(
        "Could not identify Meta Ads CSV type from its headers."
    )


def _normalize_row(
    source_row: dict,
    header_map: dict[str, str],
    *,
    filename: str,
    row_number: int,
) -> dict:
    normalized: dict = {}
    for source_header, value in source_row.items():
        field = header_map.get(source_header)
        if not field:
            continue
        if field in NUMERIC_FIELDS:
            normalized[field] = _parse_decimal(
                value, filename=filename, row_number=row_number, header=source_header
            )
        elif field in {"reporting_start", "reporting_end", "start_date"}:
            normalized[field] = _parse_date(
                value, filename=filename, row_number=row_number, header=source_header
            )
        elif field == "last_significant_edit":
            normalized[field] = _parse_datetime(
                value, filename=filename, row_number=row_number, header=source_header
            )
        elif field == "budget":
            try:
                normalized["budget"] = _parse_decimal(
                    value, filename=filename, row_number=row_number, header=source_header
                )
                normalized["budget_source"] = None
            except MetaAdsValidationError:
                normalized["budget"] = None
                normalized["budget_source"] = None if _is_null(value) else str(value).strip()
        else:
            normalized[field] = None if _is_null(value) else str(value).strip()
    normalized["source_row_number"] = row_number
    normalized["raw_data"] = dict(source_row)
    return normalized


def _fingerprint(file_type: str, raw_data: dict, occurrence: int) -> str:
    canonical = json.dumps(raw_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = f"{file_type}\n{canonical}\n{occurrence}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_meta_ads_csv(file_item, expected_type: str | None = None) -> ParsedMetaAdsFile:
    filename, raw = _read_upload(file_item)
    headers, source_rows = _decode_csv(filename, raw)
    detected_type = detect_file_type(headers)
    if expected_type and detected_type != expected_type:
        raise MetaAdsValidationError(
            f"{filename}: expected {FILE_LABELS[expected_type]} CSV but detected "
            f"{FILE_LABELS[detected_type]} CSV."
        )
    file_type = expected_type or detected_type
    header_map = {
        header: canonical_header(header)
        for header in headers
        if canonical_header(header)
    }
    canonical_headers = set(header_map.values())
    missing = sorted(REQUIRED_FIELDS[file_type] - canonical_headers)
    if missing:
        raise MetaAdsValidationError(
            f"{filename}: {FILE_LABELS[file_type]} CSV is missing required fields: "
            f"{', '.join(missing)}."
        )

    normalized_rows = [
        _normalize_row(row, header_map, filename=filename, row_number=index)
        for index, row in enumerate(source_rows, start=2)
    ]
    entity_field = ENTITY_FIELD[file_type]
    summary_rows = [row for row in normalized_rows if not row.get(entity_field)]
    detail_rows = [row for row in normalized_rows if row.get(entity_field)]
    if not detail_rows:
        raise MetaAdsValidationError(
            f"{filename}: {FILE_LABELS[file_type]} CSV contains no entity rows."
        )

    periods = {
        (row.get("reporting_start"), row.get("reporting_end"))
        for row in normalized_rows
    }
    if None in {value for period in periods for value in period}:
        raise MetaAdsValidationError(
            f"{filename}: every row must contain reporting start and end dates."
        )
    if len(periods) != 1:
        raise MetaAdsValidationError(
            f"{filename}: rows contain inconsistent reporting periods."
        )
    period_start, period_end = next(iter(periods))
    if period_end < period_start:
        raise MetaAdsValidationError(
            f"{filename}: reporting end precedes reporting start."
        )

    warnings = []
    if not summary_rows:
        warnings.append("Meta summary row was not found.")
    elif len(summary_rows) > 1:
        raise MetaAdsValidationError(
            f"{filename}: found {len(summary_rows)} rows without {entity_field}; expected one summary row."
        )
    elif normalized_rows[0] is not summary_rows[0]:
        warnings.append("Meta summary row was found but it is not the first data row.")

    raw_occurrences: Counter[str] = Counter()
    completed_rows = []
    for row in detail_rows:
        raw_json = json.dumps(row["raw_data"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        occurrence = raw_occurrences[raw_json]
        raw_occurrences[raw_json] += 1
        row["source_row_key"] = _fingerprint(file_type, row["raw_data"], occurrence)
        completed_rows.append(row)

    unknown_headers = [header for header in headers if header not in header_map]
    if unknown_headers:
        warnings.append(
            "Unmapped columns were retained in raw_data: " + ", ".join(unknown_headers)
        )
    summary = summary_rows[0] if summary_rows else None
    return ParsedMetaAdsFile(
        file_type=file_type,
        filename=filename,
        headers=tuple(headers),
        canonical_headers=tuple(sorted(canonical_headers)),
        rows=tuple(completed_rows),
        summary_row=summary,
        summary_raw_data=(dict(summary["raw_data"]) if summary else None),
        warnings=tuple(warnings),
    )


def decimal_ratio(numerator, denominator, multiplier=Decimal("1")) -> Decimal | None:
    if numerator is None or denominator in (None, 0, Decimal("0")):
        return None
    return (Decimal(numerator) / Decimal(denominator)) * multiplier


def derived_metrics(row: dict) -> dict[str, Decimal | None]:
    spend = row.get("spend")
    impressions = row.get("impressions")
    reach = row.get("reach")
    engagements = row.get("post_engagements")
    clicks = row.get("link_clicks")
    return {
        "engagement_rate": decimal_ratio(engagements, impressions),
        "cost_per_engagement": decimal_ratio(spend, engagements),
        "cost_per_reach": decimal_ratio(spend, reach),
        "cpm": decimal_ratio(spend, impressions, Decimal("1000")),
        "cpc": decimal_ratio(spend, clicks),
    }
