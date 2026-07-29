from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from sqlalchemy import text

try:
    from dashboard.config import BASE_DIR
    from dashboard.db import create_db_engine
except ModuleNotFoundError:
    from config import BASE_DIR
    from db import create_db_engine


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def report_context(client_id: str, period_id: str) -> dict:
    engine = create_db_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT c.client_code, rp.period_start
                    FROM clients c
                    JOIN report_periods rp ON rp.client_id = c.id
                    WHERE c.id = CAST(:client_id AS UUID)
                      AND rp.id = CAST(:period_id AS UUID)
                    """
                ),
                {"client_id": client_id, "period_id": period_id},
            ).mappings().first()
    finally:
        engine.dispose()

    if not row:
        raise ValueError("Client or report period was not found.")
    return dict(row)


def load_agentic_graph():
    agentic_dir = Path(BASE_DIR) / "agentic"
    if not agentic_dir.exists():
        raise RuntimeError("Agentic runtime is not available in this deployment.")
    if str(agentic_dir) not in sys.path:
        sys.path.insert(0, str(agentic_dir))

    graph_module = importlib.import_module("CentralArch.graph")
    state_module = importlib.import_module("CentralArch.state")
    agentic_graph = graph_module.app
    Request = state_module.Request
    State = state_module.State

    return agentic_graph, Request, State


def generate_agentic_report(
    client_id: str,
    period_id: str,
    dry_run: bool = False,
) -> dict:
    context = report_context(client_id, period_id)
    agentic_graph, Request, State = load_agentic_graph()

    initial_state = State(
        request=Request(
            user_intent="Analyze social media performance and generate report",
            client_code=context["client_code"],
            report_date=context["period_start"],
            generate_slides=True,
            slides_dry_run=dry_run,
            persist_insights=(
                not dry_run
                and env_bool("AGENTIC_PERSIST_INSIGHTS", True)
            ),
            reuse_cached_insights=env_bool("AGENTIC_REUSE_CACHED_INSIGHTS", False),
        )
    )
    result = agentic_graph.invoke(initial_state)
    generation = result["report_generation"]
    payload = (
        generation.model_dump()
        if hasattr(generation, "model_dump")
        else dict(generation)
    )
    if payload.get("status") == "failed":
        raise RuntimeError(payload.get("error") or "Agentic report generation failed.")

    payload["analysis_cache_hit"] = bool(result.get("analysis_cache_hit"))
    return payload
