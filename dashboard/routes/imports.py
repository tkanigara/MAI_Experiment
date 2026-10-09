from __future__ import annotations

from http import HTTPStatus

try:
    from dashboard.repositories.dashboard_repository import CSV_IMPORT_SLOTS
    from dashboard.services.csv_import import import_report_csv
    from dashboard.services.meta_ads_import import import_meta_ads_csv
except ModuleNotFoundError:
    from repositories.dashboard_repository import CSV_IMPORT_SLOTS
    from services.csv_import import import_report_csv
    from services.meta_ads_import import import_meta_ads_csv


META_ADS_SLOTS = (
    "campaign",
    "adset",
    "ad",
    "placement",
    "demographic",
    "region",
)


def handle_post(handler, parsed) -> bool:
    if parsed.path not in {
        "/api/import/csv",
        "/api/import/meta-ads",
        "/api/ads/imports",
    }:
        return False

    try:
        fields = handler.parse_multipart()
        if parsed.path in {"/api/import/meta-ads", "/api/ads/imports"}:
            payload = {
                "client_id": fields.get("client_id"),
                "period_id": fields.get("period_id"),
            }
            files = {slot: fields.get(slot) for slot in META_ADS_SLOTS}
            handler.send_json(
                import_meta_ads_csv(handler.repository, payload, files),
                HTTPStatus.CREATED,
            )
            return True
        payload = {
            "client_id": fields.get("client_id"),
            "month_slug": fields.get("month_slug"),
        }
        files = {slot: fields.get(slot) for slot in CSV_IMPORT_SLOTS}
        handler.send_json(import_report_csv(handler.repository, payload, files), HTTPStatus.CREATED)
    except ValueError as exc:
        handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
    return True
