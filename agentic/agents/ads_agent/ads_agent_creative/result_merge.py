"""Helpers for combining multiple objective analyses without data loss."""

from __future__ import annotations

from typing import TypeVar

from agentic.workflows.ads_workflow.ads_creative_workflow.state import (
    ObjectiveMetricAnalysis,
)


T = TypeVar("T")


def normalise_objective(value: str | None) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _first_value(data: dict, names: list[str]):
    for name in names:
        value = data.get(name)
        if value is not None:
            return value
    return None


def _objective_analysis(data: dict, objective: str) -> ObjectiveMetricAnalysis:
    suffix = normalise_objective(objective)

    def values(*bases: str):
        candidates = [f"{base}_{suffix}" for base in bases]
        candidates.extend(bases)
        return _first_value(data, candidates)

    error = data.get("analysis_error")
    analysis = ObjectiveMetricAnalysis(
        objective=suffix,
        status="error" if error else "ready",
        error=error,
        performance_overview=values("performance_overview"),
        content_analysis=values("content_analysis"),
        placement_analysis=values("placement_analysis"),
        audience_demographic_analysis=values(
            "audience_demographic_analysis",
            "audience_demographics",
            "audience_demographic",
        ),
        region_analysis=values("region_analysis", "region_breakdown"),
        testing_optimization=values("testing_optimization"),
        bidding_optimisation=values("bidding_optimisation"),
        optimisation_action=values("optimisation_action", "optimisation"),
    )
    if not error and not any(
        value
        for key, value in analysis.model_dump().items()
        if key not in {"objective", "status", "error"}
    ):
        analysis.status = "unavailable"
    return analysis


def merge_objective_result(current: T | None, new_result: T) -> T:
    """Merge legacy fields and retain a canonical result per objective."""

    model_type = type(new_result)
    current_data = current.model_dump() if current is not None else {}
    new_data = new_result.model_dump()
    objective = normalise_objective(new_data.get("objective"))

    merged = dict(current_data)
    for field, value in new_data.items():
        if field not in {"objective", "objectives", "objective_results"} and value is not None:
            merged[field] = value

    objectives = list(current_data.get("objectives") or [])
    results = dict(current_data.get("objective_results") or {})
    if objective:
        if objective not in objectives:
            objectives.append(objective)
        results[objective] = _objective_analysis(new_data, objective).model_dump()

    merged["objectives"] = objectives
    merged["objective_results"] = results
    merged["objective"] = objectives[0] if len(objectives) == 1 else None
    return model_type(**merged)
