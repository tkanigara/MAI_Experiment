from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.tools import tool


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.services.slides_report import generate_report_slides  # noqa: E402


@tool
def generate_slides_report(
    client_id: str,
    report_period_id: str,
    dry_run: bool = False,
    insight_overrides: list[dict] | None = None,
) -> dict:
    """Generate a Google Slides report, optionally using insights from agent state."""
    try:
        result = generate_report_slides(
            client_id=client_id,
            period_id=report_period_id,
            dry_run=dry_run,
            insight_overrides=insight_overrides,
        )
        if dry_run:
            return {
                "status": "dry_run_completed",
                "presentation_id": None,
                "presentation_url": None,
                "report_name": None,
                "diagnostics": result,
            }
        return {
            "status": "completed",
            "presentation_id": result.get("presentation_id"),
            "presentation_url": result.get("presentation_url"),
            "report_name": result.get("report_name"),
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "presentation_id": None,
            "presentation_url": None,
            "report_name": None,
            "error": str(exc),
        }
