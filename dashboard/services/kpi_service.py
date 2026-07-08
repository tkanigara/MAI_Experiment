from __future__ import annotations

try:
    from dashboard.repositories.dashboard_repository import DashboardRepository
except ModuleNotFoundError:
    from repositories.dashboard_repository import DashboardRepository


def upsert_kpi_target(repository: DashboardRepository, payload: dict) -> dict:
    return repository.upsert_kpi_target(payload)
