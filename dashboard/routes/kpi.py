from __future__ import annotations

import json
from http import HTTPStatus

try:
    from dashboard.services.kpi_service import upsert_kpi_target
except ModuleNotFoundError:
    from services.kpi_service import upsert_kpi_target


def handle_post(handler, parsed) -> bool:
    if parsed.path != "/api/kpi-targets":
        return False

    length = int(handler.headers.get("Content-Length", "0"))
    try:
        payload = json.loads(handler.rfile.read(length) or b"{}")
        handler.send_json(upsert_kpi_target(handler.repository, payload), HTTPStatus.CREATED)
    except (json.JSONDecodeError, ValueError) as exc:
        handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
    return True
