from __future__ import annotations

from typing import Callable

try:
    from dashboard.slides_report import generate_dashboard_slides_report
except ModuleNotFoundError:
    from slides_report import generate_dashboard_slides_report


def generate_report_slides(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
    insight_overrides: list[dict] | None = None,
    existing_presentation_id: str | None = None,
    existing_report_name: str | None = None,
    on_presentation_created: Callable[[dict], None] | None = None,
) -> dict:
    return generate_dashboard_slides_report(
        client_id=client_id,
        period_id=period_id,
        dry_run=dry_run,
        insight_overrides=insight_overrides,
        existing_presentation_id=existing_presentation_id,
        existing_report_name=existing_report_name,
        on_presentation_created=on_presentation_created,
    )
