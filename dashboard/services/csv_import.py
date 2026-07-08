from __future__ import annotations

try:
    from dashboard.repositories.dashboard_repository import DashboardRepository
except ModuleNotFoundError:
    from repositories.dashboard_repository import DashboardRepository


def import_report_csv(repository: DashboardRepository, payload: dict, files: dict) -> dict:
    return repository.import_csv_report(payload, files)
