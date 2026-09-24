"""Resolve Ad Set evidence from a frozen report payload or the dashboard."""

from __future__ import annotations

from typing import Any


ALIASES = {
    "linkclicks": "link_clicks",
}


def get_adset_evidence(state, objective: str, retrieval_tool) -> dict[str, Any]:
    """Prefer evidence injected by the report generator.

    Interactive agent runs still use the objective retrieval tool. Report
    generation injects the exact payload used by the slide mapping so the LLM
    cannot analyse a newer or differently filtered snapshot.
    """

    objective_key = ALIASES.get(str(objective).strip().lower(), str(objective).strip().lower())
    cached = (state.adset_data or {}).get(objective_key)
    if cached:
        return cached
    return retrieval_tool.invoke(
        {
            "client_code": state.request.client_code,
            "period_id": state.request.period_id,
            "campaign_ids": state.request.campaign_ids,
            "adset_ids": state.request.adset_ids,
        }
    )
