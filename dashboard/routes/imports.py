from __future__ import annotations

from http import HTTPStatus

try:
    from dashboard.repositories.dashboard_repository import CSV_IMPORT_SLOTS
    from dashboard.services.csv_import import import_report_csv
except ModuleNotFoundError:
    from repositories.dashboard_repository import CSV_IMPORT_SLOTS
    from services.csv_import import import_report_csv


def handle_post(handler, parsed) -> bool:
    if parsed.path != "/api/import/csv":
        return False

    try:
        fields = handler.parse_multipart()
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
