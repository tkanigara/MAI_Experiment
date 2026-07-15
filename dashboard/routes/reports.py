from __future__ import annotations

import json
from http import HTTPStatus

try:
    from dashboard.repositories.dashboard_repository import parse_bool
    from dashboard.schemas import require_fields
    from dashboard.services.agentic_report import generate_agentic_report
except ModuleNotFoundError:
    from repositories.dashboard_repository import parse_bool
    from schemas import require_fields
    from services.agentic_report import generate_agentic_report


def handle_post(handler, parsed) -> bool:
    if parsed.path != "/api/reports/slides":
        return False

    length = int(handler.headers.get("Content-Length", "0"))
    try:
        payload = json.loads(handler.rfile.read(length) or b"{}")
        client_id = str(payload.get("client_id") or "").strip()
        period_id = str(payload.get("period_id") or "").strip()
        require_fields({"client_id": client_id, "period_id": period_id}, ["client_id", "period_id"])
        handler.send_json(
            generate_agentic_report(
                client_id=client_id,
                period_id=period_id,
                dry_run=parse_bool(payload.get("dry_run")),
            ),
            HTTPStatus.CREATED,
        )
    except ValueError as exc:
        handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
    return True
