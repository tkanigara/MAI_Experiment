from __future__ import annotations

from typing import Callable

try:
    from dashboard.slides_report import (
        cleanup_cancelled_presentation as cleanup_presentation,
        generate_dashboard_slides_report,
    )
    from dashboard.ads_slides_report import generate_ads_slides_report
except ModuleNotFoundError:
    from slides_report import (
        cleanup_cancelled_presentation as cleanup_presentation,
        generate_dashboard_slides_report,
    )
    from ads_slides_report import generate_ads_slides_report


def generate_report_slides(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
    insight_overrides: list[dict] | None = None,
    existing_presentation_id: str | None = None,
    existing_report_name: str | None = None,
    on_presentation_created: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> dict:
    return generate_dashboard_slides_report(
        client_id=client_id,
        period_id=period_id,
        dry_run=dry_run,
        insight_overrides=insight_overrides,
        existing_presentation_id=existing_presentation_id,
        existing_report_name=existing_report_name,
        on_presentation_created=on_presentation_created,
        should_cancel=should_cancel,
        on_stage=on_stage,
    )


def generate_ads_report_slides(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
    report_model: str = "jba",
    platform_scope: str | None = None,
    objective: str | None = None,
    existing_presentation_id: str | None = None,
    existing_report_name: str | None = None,
    on_presentation_created: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> dict:
    return generate_ads_slides_report(
        client_id=client_id,
        period_id=period_id,
        dry_run=dry_run,
        report_model=report_model,
        platform_scope=platform_scope,
        objective=objective,
        existing_presentation_id=existing_presentation_id,
        existing_report_name=existing_report_name,
        on_presentation_created=on_presentation_created,
        should_cancel=should_cancel,
        on_stage=on_stage,
    )


def cleanup_cancelled_presentation(
    presentation_id: str,
    report_name: str | None = None,
) -> dict:
    return cleanup_presentation(presentation_id, report_name)
