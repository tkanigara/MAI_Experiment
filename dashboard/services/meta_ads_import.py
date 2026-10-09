from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from uuid import UUID

try:
    from dashboard.repositories.meta_ads_repository import MetaAdsRepository
    from dashboard.services.meta_ads_csv import (
        FILE_LABELS,
        META_ADS_FILE_TYPES,
        MetaAdsValidationError,
        ParsedMetaAdsFile,
        parse_meta_ads_csv,
    )
except ModuleNotFoundError:
    from repositories.meta_ads_repository import MetaAdsRepository
    from services.meta_ads_csv import (
        FILE_LABELS,
        META_ADS_FILE_TYPES,
        MetaAdsValidationError,
        ParsedMetaAdsFile,
        parse_meta_ads_csv,
    )


ADDITIVE_METRICS = (
    "spend",
    "impressions",
    "post_engagements",
    "link_clicks",
    "instagram_follows",
    "page_engagements",
)


def _sum(rows, field: str) -> Decimal:
    return sum(
        (row.get(field) for row in rows if row.get(field) is not None),
        Decimal("0"),
    )


def _close(actual: Decimal | None, expected: Decimal | None) -> bool | None:
    if actual is None or expected is None:
        return None
    tolerance = max(Decimal("1"), abs(expected) * Decimal("0.000001"))
    return abs(actual - expected) <= tolerance


def _check(name: str, actual, expected, *, severity: str = "warning") -> dict:
    matched = _close(actual, expected)
    return {
        "name": name,
        "status": "unavailable" if matched is None else ("passed" if matched else "warning"),
        "severity": severity,
        "actual": actual,
        "expected": expected,
        "difference": None if actual is None or expected is None else actual - expected,
    }


def _summary_value(parsed: ParsedMetaAdsFile, field: str):
    return (parsed.summary_row or {}).get(field)


def build_import_diagnostics(files: dict[str, ParsedMetaAdsFile]) -> tuple[dict, list[str]]:
    campaign = files["campaign"]
    ad = files["ad"]
    warnings: list[str] = []
    checks = []

    for file_type, parsed in files.items():
        for metric in ("spend", "impressions"):
            checks.append(
                _check(
                    f"{file_type}_detail_{metric}_to_summary",
                    _sum(parsed.rows, metric),
                    _summary_value(parsed, metric),
                )
            )

    for file_type in ("adset", "ad", "placement", "demographic", "region"):
        for metric in ("spend", "impressions"):
            checks.append(
                _check(
                    f"{file_type}_{metric}_to_campaign",
                    _sum(files[file_type].rows, metric),
                    _sum(campaign.rows, metric),
                )
            )

    for check in checks:
        if check["status"] == "warning":
            warnings.append(
                f"Reconciliation warning: {check['name']} differs by {check['difference']}."
            )

    id_availability = {
        "campaign_external_id": any(
            "campaign_external_id" in parsed.canonical_headers for parsed in files.values()
        ),
        "adset_external_id": any(
            "adset_external_id" in parsed.canonical_headers for parsed in files.values()
        ),
        "ad_external_id": any(
            "ad_external_id" in parsed.canonical_headers for parsed in files.values()
        ),
    }
    missing_ids = [name for name, available in id_availability.items() if not available]
    if missing_ids:
        warnings.append(
            "External Meta entity IDs are unavailable: " + ", ".join(missing_ids) + "."
        )

    adset_names = [row.get("adset_name") for row in files["adset"].rows]
    ad_pairs = [(row.get("adset_name"), row.get("ad_name")) for row in ad.rows]
    duplicated_adsets = sorted(
        name for name, count in Counter(adset_names).items() if name and count > 1
    )
    duplicated_ad_pairs = sum(count - 1 for count in Counter(ad_pairs).values() if count > 1)
    relationships_reliable = bool(
        id_availability["campaign_external_id"]
        and id_availability["adset_external_id"]
        and id_availability["ad_external_id"]
    )
    if not relationships_reliable:
        warnings.append(
            "Campaign to ad set to ad relationships were not inferred; repeated names make name-based foreign keys unsafe."
        )

    canonical_totals = {
        metric: _sum(campaign.rows, metric) for metric in ADDITIVE_METRICS
    }
    # Reach and frequency are non-additive. The total row is retained only in
    # import metadata so reports can use Meta's account-level deduplicated value.
    canonical_totals.update(
        {
            "reach": _summary_value(campaign, "reach"),
            "frequency": _summary_value(campaign, "frequency"),
            "source": "campaign",
            "non_additive_source": "campaign_summary_metadata",
        }
    )

    result_types = sorted(
        {
            row.get("result_type")
            for parsed in files.values()
            for row in parsed.rows
            if row.get("result_type")
        }
    )
    summary_rows = {
        file_type: {
            "present": parsed.summary_row is not None,
            "source_row_number": (
                parsed.summary_row.get("source_row_number") if parsed.summary_row else None
            ),
            "raw_data": parsed.summary_raw_data,
        }
        for file_type, parsed in files.items()
    }
    diagnostics = {
        "canonical_level": "campaign",
        "canonical_totals": canonical_totals,
        "summary_rows": summary_rows,
        "checks": checks,
        "result_types": result_types,
        "id_availability": id_availability,
        "relationships": {
            "reliable": relationships_reliable,
            "strategy": "external_ids_only",
            "duplicated_adset_names": duplicated_adsets,
            "duplicate_adset_ad_rows": duplicated_ad_pairs,
        },
        "file_row_counts": {
            file_type: len(parsed.rows) for file_type, parsed in files.items()
        },
    }
    return diagnostics, warnings


class MetaAdsImportService:
    def __init__(self, repository: MetaAdsRepository):
        self.repository = repository

    def import_files(self, payload: dict, file_items: dict) -> dict:
        client_id = str(payload.get("client_id") or "").strip()
        if not client_id:
            raise MetaAdsValidationError("Missing client_id.")
        try:
            UUID(client_id)
        except ValueError as exc:
            raise MetaAdsValidationError("client_id must be a UUID.") from exc

        missing_files = [
            FILE_LABELS[file_type]
            for file_type in META_ADS_FILE_TYPES
            if not file_items.get(file_type)
            or not getattr(file_items[file_type], "filename", "")
        ]
        if missing_files:
            raise MetaAdsValidationError(
                "All six Meta Ads CSV files are required. Missing: "
                + ", ".join(missing_files)
                + "."
            )

        parsed_files = {
            file_type: parse_meta_ads_csv(file_items[file_type], expected_type=file_type)
            for file_type in META_ADS_FILE_TYPES
        }
        periods = {parsed.period for parsed in parsed_files.values()}
        if len(periods) != 1:
            details = ", ".join(
                f"{file_type}={parsed.period[0]}..{parsed.period[1]}"
                for file_type, parsed in parsed_files.items()
            )
            raise MetaAdsValidationError(
                "The six Meta Ads files do not share one reporting period: " + details
            )
        period_start, period_end = next(iter(periods))

        diagnostics, warnings = build_import_diagnostics(parsed_files)
        for file_type, parsed in parsed_files.items():
            warnings.extend(
                f"{FILE_LABELS[file_type]}: {warning}" for warning in parsed.warnings
            )

        stored = self.repository.import_snapshot(
            client_id=client_id,
            requested_period_id=(str(payload.get("period_id") or "").strip() or None),
            period_start=period_start,
            period_end=period_end,
            files=parsed_files,
            diagnostics=diagnostics,
            warnings=warnings,
        )
        return {
            "import": {
                "id": stored["import_id"],
                "source": "csv",
                "platform": "meta",
                "status": "success",
            },
            "period": {
                "id": stored["meta_ads_report_period_id"],
                "start": period_start,
                "end": period_end,
            },
            "counts": stored["counts"],
            "warnings": warnings,
            "diagnostics": diagnostics,
            "files": {
                file_type: {
                    "filename": parsed.filename,
                    "headers": list(parsed.headers),
                    "rows_imported": len(parsed.rows),
                    "summary_rows_skipped": 1 if parsed.summary_row else 0,
                }
                for file_type, parsed in parsed_files.items()
            },
        }


def import_meta_ads_csv(repository, payload: dict, files: dict) -> dict:
    engine = getattr(repository, "engine", repository)
    return MetaAdsImportService(MetaAdsRepository(engine)).import_files(payload, files)
