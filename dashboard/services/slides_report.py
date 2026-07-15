from __future__ import annotations

try:
    from dashboard.slides_report import generate_dashboard_slides_report
except ModuleNotFoundError:
    from slides_report import generate_dashboard_slides_report


def generate_report_slides(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
    insight_overrides: list[dict] | None = None,
) -> dict:
    return generate_dashboard_slides_report(
        client_id=client_id,
        period_id=period_id,
        dry_run=dry_run,
        insight_overrides=insight_overrides,
    )
