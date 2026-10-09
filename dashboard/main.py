from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool

try:
    from dashboard.config import DASHBOARD_DIR, STATIC_DIR
    from dashboard.repositories.dashboard_repository import (
        CSV_IMPORT_SLOTS,
        DashboardRepository,
        ReportPeriodAlreadyExistsError,
        json_safe,
        parse_bool,
    )
    from dashboard.repositories.report_job_repository import (
        ActiveReportJobError,
        ReportJobNotFoundError,
        ReportJobRepository,
        ReportJobTransitionError,
    )
    from dashboard.repositories.meta_ads_repository import MetaAdsRepository
    from dashboard.repositories.report_data_lock import ReportDataLockedError
    from dashboard.schemas import require_fields
    from dashboard.services.csv_import import import_report_csv
    from dashboard.services.ads_workspace import ads_platform_catalog
    from dashboard.services.ads_objectives import objective_catalog
    from dashboard.services.meta_ads_import import import_meta_ads_csv
    from dashboard.services.meta_ads_api import MetaAdsApiClient, MetaAdsApiError, MetaAdsSyncService
    from dashboard.services.kpi_service import upsert_kpi_target
    from dashboard.services.agentic_report import generate_agentic_report
    from dashboard.services.report_editor import ReportEditorService
    from dashboard.services.report_jobs import (
        ReportJobAlreadyRunningError,
        ReportJobWorker,
        ReportTaskAuthenticationError,
        ReportJobService,
        ReportQueueUnavailableError,
        ReportTaskDispatchError,
        RetryableReportJobError,
        build_report_task_dispatcher,
        verify_cloud_tasks_oidc,
        verify_report_task_request,
    )
except ModuleNotFoundError:
    from config import DASHBOARD_DIR, STATIC_DIR
    from repositories.dashboard_repository import (
        CSV_IMPORT_SLOTS,
        DashboardRepository,
        ReportPeriodAlreadyExistsError,
        json_safe,
        parse_bool,
    )
    from repositories.report_job_repository import (
        ActiveReportJobError,
        ReportJobNotFoundError,
        ReportJobRepository,
        ReportJobTransitionError,
    )
    from repositories.meta_ads_repository import MetaAdsRepository
    from repositories.report_data_lock import ReportDataLockedError
    from schemas import require_fields
    from services.csv_import import import_report_csv
    from services.ads_workspace import ads_platform_catalog
    from services.ads_objectives import objective_catalog
    from services.meta_ads_import import import_meta_ads_csv
    from services.meta_ads_api import MetaAdsApiClient, MetaAdsApiError, MetaAdsSyncService
    from services.kpi_service import upsert_kpi_target
    from services.agentic_report import generate_agentic_report
    from services.report_editor import ReportEditorService
    from services.report_jobs import (
        ReportJobAlreadyRunningError,
        ReportJobWorker,
        ReportTaskAuthenticationError,
        ReportJobService,
        ReportQueueUnavailableError,
        ReportTaskDispatchError,
        RetryableReportJobError,
        build_report_task_dispatcher,
        verify_cloud_tasks_oidc,
        verify_report_task_request,
    )


repository = DashboardRepository()
meta_ads_repository = MetaAdsRepository(repository.engine)
meta_ads_api = MetaAdsApiClient()
meta_ads_sync = MetaAdsSyncService(meta_ads_repository, meta_ads_api)
report_editor = ReportEditorService(repository.engine)
report_job_repository = ReportJobRepository(repository.engine)
report_job_worker = ReportJobWorker(
    report_job_repository,
    generate_agentic_report,
    lease_seconds=int(os.getenv("REPORT_JOB_LEASE_SECONDS", "900")),
)
report_jobs = ReportJobService(
    report_job_repository,
    build_report_task_dispatcher(report_job_worker.execute),
)
app = FastAPI(title="MAI Social Media Dashboard API")


@app.exception_handler(HTTPException)
def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(content={"error": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(content={"error": str(exc)}, status_code=422)


@app.exception_handler(ReportDataLockedError)
def report_data_locked_handler(_request: Request, exc: ReportDataLockedError):
    return JSONResponse(
        content={
            "error": str(exc),
            "code": exc.code,
            "job": json_safe(exc.job),
        },
        status_code=409,
    )


@app.exception_handler(ReportPeriodAlreadyExistsError)
def report_period_already_exists_handler(
    _request: Request,
    exc: ReportPeriodAlreadyExistsError,
):
    return JSONResponse(
        content={
            "error": str(exc),
            "code": exc.code,
            "period": json_safe(exc.period),
        },
        status_code=409,
    )


def json_response(payload, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=json_safe(payload), status_code=status_code)


def bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def duplicate_client_message(exc: Exception) -> str:
    message = str(exc)
    if "duplicate key value" in message and "clients_client_code_key" in message:
        return "Client code already exists."
    return message


def hydrate_meta_account_payload(payload: dict | None) -> dict:
    result = dict(payload or {})
    if "meta_ad_account_ids" not in result:
        return result
    selected = {str(item) for item in result.get("meta_ad_account_ids") or []}
    if not selected:
        result["_meta_ad_accounts"] = []
        return result
    accounts = meta_ads_api.ad_accounts()
    indexed = {account["id"]: account for account in accounts}
    missing = selected.difference(indexed)
    if missing:
        raise ValueError("One or more selected Meta Ad Accounts are not accessible.")
    inactive = [indexed[item]["name"] for item in selected if not indexed[item]["is_active"]]
    if inactive:
        raise ValueError("Inactive Meta Ad Accounts cannot be selected: " + ", ".join(inactive))
    result["_meta_ad_accounts"] = [indexed[item] for item in selected]
    return result


@app.get("/api/clients")
def get_clients(product: Optional[str] = None):
    try:
        return json_response(repository.clients(product))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/client-products/summary")
def get_client_product_summary():
    return json_response(repository.client_product_summary())


@app.post("/api/clients/{client_id}/products/{product}")
def activate_client_product(client_id: str, product: str, payload: Optional[dict] = None):
    try:
        if product == "meta_ads":
            payload = hydrate_meta_account_payload(payload)
        return json_response(
            repository.activate_client_product(client_id, product, payload),
            status_code=201,
        )
    except ValueError as exc:
        raise bad_request(exc)
    except MetaAdsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))


@app.delete("/api/clients/{client_id}/products/{product}")
def deactivate_client_product(client_id: str, product: str):
    try:
        return json_response(repository.deactivate_client_product(client_id, product))
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/clients")
def create_client(payload: dict):
    try:
        if str(payload.get("product") or "social_media") == "meta_ads":
            payload = hydrate_meta_account_payload(payload)
        return json_response(repository.create_client(payload), status_code=201)
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=duplicate_client_message(exc))


@app.post("/api/clients/{client_id}")
@app.put("/api/clients/{client_id}")
def update_client(client_id: str, payload: dict):
    try:
        return json_response(repository.update_client(client_id, payload))
    except ReportDataLockedError:
        raise
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=duplicate_client_message(exc))


@app.delete("/api/clients")
def delete_client_missing_id():
    raise HTTPException(status_code=400, detail="Client id is required")


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: str):
    try:
        return json_response(repository.delete_client(client_id))
    except ReportDataLockedError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/clients/{client_id}/report-periods/{period_id}")
def delete_report_period(client_id: str, period_id: str):
    try:
        return json_response(repository.delete_report_period(client_id, period_id))
    except ReportDataLockedError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/clients/{client_id}/report-periods/{period_id}")
def update_report_period(client_id: str, period_id: str, payload: dict):
    try:
        return json_response(
            repository.update_report_period(client_id, period_id, payload)
        )
    except (ReportDataLockedError, ReportPeriodAlreadyExistsError):
        raise
    except MetaAdsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    except MetaAdsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    except ValueError as exc:
        raise bad_request(exc)
    except MetaAdsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/clients/{client_id}/platforms")
def get_platforms(client_id: str):
    try:
        return json_response(repository.platforms(client_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/clients/{client_id}/platforms/{platform}/overview")
def get_platform_overview(client_id: str, platform: str, period_id: Optional[str] = None):
    try:
        return json_response(repository.overview(client_id, platform, period_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/import/csv")
def import_csv(
    client_id: str = Form(...),
    month_slug: str = Form(...),
    period_id: Optional[str] = Form(None),
    account: Optional[UploadFile] = File(None),
    competitor: Optional[UploadFile] = File(None),
    competitor_content: Optional[UploadFile] = File(None),
    all_content: Optional[UploadFile] = File(None),
    ig_post: Optional[UploadFile] = File(None),
    ig_story: Optional[UploadFile] = File(None),
    fb_post: Optional[UploadFile] = File(None),
    tt_post: Optional[UploadFile] = File(None),
    yt_post: Optional[UploadFile] = File(None),
):
    files = {
        "account": account,
        "competitor": competitor,
        "competitor_content": competitor_content,
        "all_content": all_content,
        "ig_post": ig_post,
        "ig_story": ig_story,
        "fb_post": fb_post,
        "tt_post": tt_post,
        "yt_post": yt_post,
    }
    try:
        payload = {
            "client_id": client_id,
            "month_slug": month_slug,
            "period_id": period_id,
        }
        return json_response(import_report_csv(repository, payload, files), status_code=201)
    except (ReportDataLockedError, ReportPeriodAlreadyExistsError):
        raise
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for slot in CSV_IMPORT_SLOTS:
            file_item = files.get(slot)
            if file_item is not None:
                file_item.file.close()


@app.post("/api/import/meta-ads")
@app.post("/api/ads/imports")
def import_meta_ads(
    client_id: str = Form(...),
    period_id: Optional[str] = Form(None),
    campaign: UploadFile = File(...),
    adset: UploadFile = File(...),
    ad: UploadFile = File(...),
    placement: UploadFile = File(...),
    demographic: UploadFile = File(...),
    region: UploadFile = File(...),
):
    files = {
        "campaign": campaign,
        "adset": adset,
        "ad": ad,
        "placement": placement,
        "demographic": demographic,
        "region": region,
    }
    try:
        return json_response(
            import_meta_ads_csv(
                repository,
                {"client_id": client_id, "period_id": period_id},
                files,
            ),
            status_code=201,
        )
    except ReportDataLockedError:
        raise
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for file_item in files.values():
            file_item.file.close()


@app.get("/api/ads/clients/{client_id}/periods")
def get_meta_ads_periods(client_id: str):
    try:
        return json_response(meta_ads_repository.client_periods(client_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/platforms")
def get_ads_platforms():
    return json_response(ads_platform_catalog())


@app.get("/api/ads/objective-catalog")
def get_ads_objective_catalog():
    return json_response(objective_catalog())


@app.get("/api/ads/clients/{client_id}/metric-configurations")
def get_ads_metric_configurations(client_id: str):
    try:
        return json_response(meta_ads_repository.metric_configurations(client_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.put("/api/ads/clients/{client_id}/metric-configurations/{scope}/{objective}")
def save_ads_metric_configuration(client_id: str, scope: str, objective: str, payload: dict):
    try:
        return json_response(meta_ads_repository.save_metric_configuration(client_id, scope, objective, payload))
    except ValueError as exc:
        raise bad_request(exc)


@app.delete("/api/ads/clients/{client_id}/metric-configurations/{scope}/{objective}")
def reset_ads_metric_configuration(client_id: str, scope: str, objective: str):
    try:
        return json_response(meta_ads_repository.reset_metric_configuration(client_id, scope, objective))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/meta/status")
def get_meta_ads_status():
    return json_response(meta_ads_api.status())


@app.get("/api/ads/meta/ad-accounts")
def get_meta_ad_accounts():
    try:
        return json_response(meta_ads_api.ad_accounts())
    except MetaAdsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))


@app.post("/api/ads/clients/{client_id}/periods")
def create_ads_period(client_id: str, payload: dict):
    try:
        return json_response(meta_ads_repository.create_period(client_id, payload), status_code=201)
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/ads/clients/{client_id}/periods/{period_id}/sync")
def sync_meta_ads(client_id: str, period_id: str, payload: dict):
    try:
        return json_response(meta_ads_sync.sync(client_id, period_id, payload), status_code=201)
    except MetaAdsApiError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/sources")
def get_ads_sources(client_id: str, period_id: str):
    try:
        return json_response(meta_ads_repository.sources(client_id, period_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/editor")
def get_ads_data_editor(client_id: str, period_id: str):
    try:
        return json_response(meta_ads_repository.data_editor(client_id, period_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.patch("/api/ads/clients/{client_id}/periods/{period_id}/editor/{entity_type}")
def save_ads_data_editor(client_id: str, period_id: str, entity_type: str, payload: dict):
    try:
        return json_response(meta_ads_repository.save_data_editor(client_id, period_id, entity_type, payload))
    except RuntimeError as exc:
        if str(exc).startswith("VERSION_CONFLICT:"):
            raise HTTPException(status_code=409, detail=str(exc).split(":", 1)[1].strip())
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/ads/clients/{client_id}/periods/{period_id}/editor/overrides/{override_id}/restore")
def restore_ads_data_override(client_id: str, period_id: str, override_id: str, payload: dict):
    try:
        return json_response(meta_ads_repository.restore_data_override(
            client_id, period_id, override_id, payload.get("actor"),
        ))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/campaign-mappings")
def get_ads_campaign_mappings(client_id: str, period_id: str):
    try:
        return json_response(meta_ads_repository.campaign_mappings(client_id, period_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.put("/api/ads/clients/{client_id}/periods/{period_id}/campaign-mappings")
def save_ads_campaign_mappings(client_id: str, period_id: str, payload: dict):
    try:
        return json_response(meta_ads_repository.save_campaign_mappings(client_id, period_id, payload))
    except ValueError as exc:
        raise bad_request(exc)


def _analysis_filters(request: Request) -> dict:
    query = request.query_params
    split = lambda key: [item for item in query.get(key, "").split(",") if item]
    return {
        "platform_scope": query.get("platform_scope", "meta"),
        "objective": query.get("objective", ""),
        "campaign_ids": split("campaign_ids"),
        "adset_ids": split("adset_ids"),
    }


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/creative-performance")
def get_ads_creative_performance(client_id: str, period_id: str, request: Request):
    try:
        return json_response(meta_ads_repository.analysis(client_id, period_id, "creative", _analysis_filters(request)))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/adset-performance")
def get_ads_adset_performance(client_id: str, period_id: str, request: Request):
    try:
        return json_response(meta_ads_repository.analysis(client_id, period_id, "adset", _analysis_filters(request)))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/adsets/{adset_id}/creatives")
def get_ads_adset_creatives(client_id: str, period_id: str, adset_id: str, request: Request):
    try:
        filters = _analysis_filters(request)
        filters["adset_ids"] = [adset_id]
        return json_response(meta_ads_repository.analysis(client_id, period_id, "creative", filters))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/creatives/{creative_id}")
def get_ads_creative_detail(client_id: str, period_id: str, creative_id: str, platform_scope: str = "meta"):
    try:
        return json_response(meta_ads_repository.creative_detail(client_id, period_id, creative_id, platform_scope))
    except ValueError as exc:
        raise bad_request(exc)


@app.put("/api/ads/clients/{client_id}/periods/{period_id}/active-source")
def select_ads_source(client_id: str, period_id: str, payload: dict):
    try:
        return json_response(meta_ads_repository.select_source(client_id, period_id, payload.get("platform"), payload.get("import_id")))
    except (TypeError, ValueError) as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/platforms/{platform}")
def get_ads_platform_detail(client_id: str, period_id: str, platform: str):
    try:
        return json_response(
            meta_ads_repository.platform_detail(client_id, period_id, platform)
        )
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/ads/clients/{client_id}/periods/{period_id}/overview")
def get_ads_period_overview(client_id: str, period_id: str):
    try:
        return json_response(meta_ads_repository.period_overview(client_id, period_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.put("/api/ads/clients/{client_id}/periods/{period_id}/configuration")
def update_ads_period_configuration(client_id: str, period_id: str, payload: dict):
    try:
        return json_response(
            meta_ads_repository.update_period_configuration(
                client_id, period_id, payload
            )
        )
    except ValueError as exc:
        raise bad_request(exc)


@app.delete("/api/ads/clients/{client_id}/periods/{period_id}")
def delete_meta_ads_period(client_id: str, period_id: str):
    try:
        return json_response(meta_ads_repository.delete_period(client_id, period_id))
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/kpi-targets")
def save_kpi_target(payload: dict):
    try:
        return json_response(upsert_kpi_target(repository, payload), status_code=201)
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/reports/slides")
def generate_slides(payload: dict):
    try:
        client_id = str(payload.get("client_id") or "").strip()
        period_id = str(payload.get("period_id") or "").strip()
        require_fields({"client_id": client_id, "period_id": period_id}, ["client_id", "period_id"])
        report_type = str(payload.get("report_type") or payload.get("product") or "social_media").strip().lower()
        if report_type in {"ads", "meta_ads", "paid_ads"}:
            try:
                from dashboard.services.slides_report import generate_ads_report_slides
            except ModuleNotFoundError:
                from services.slides_report import generate_ads_report_slides
            result = generate_ads_report_slides(
                client_id=client_id,
                period_id=period_id,
                dry_run=parse_bool(payload.get("dry_run")),
                report_model=str(payload.get("report_model") or "jba"),
                platform_scope=payload.get("platform_scope"),
                objective=payload.get("objective"),
            )
        else:
            result = generate_agentic_report(
                client_id=client_id,
                period_id=period_id,
                dry_run=parse_bool(payload.get("dry_run")),
            )
        return json_response(result, status_code=201)
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/clients/{client_id}/report-periods/{period_id}/editor"
)
def get_report_editor(client_id: str, period_id: str):
    try:
        return json_response(report_editor.get_editor(client_id, period_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch(
    "/api/clients/{client_id}/report-periods/{period_id}"
    "/editor/sections/{section}"
)
def update_report_editor_section(
    client_id: str,
    period_id: str,
    section: str,
    payload: dict,
):
    try:
        return json_response(
            report_editor.update_section(
                client_id,
                period_id,
                section,
                payload,
            )
        )
    except ReportDataLockedError:
        raise
    except RuntimeError as exc:
        if str(exc).startswith("VERSION_CONFLICT:"):
            raise HTTPException(status_code=409, detail=str(exc).split(":", 1)[1].strip())
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/clients/{client_id}/report-periods/{period_id}/assets"
)
def upload_report_asset(
    client_id: str,
    period_id: str,
    actor: str = Form(...),
    platform: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    try:
        return json_response(
            report_editor.upload_asset(
                client_id,
                period_id,
                actor,
                file.filename or "report-image",
                file.content_type or "",
                file.file.read(),
                platform,
            ),
            status_code=201,
        )
    except ReportDataLockedError:
        raise
    except ValueError as exc:
        raise bad_request(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        file.file.close()


@app.post(
    "/api/clients/{client_id}/report-periods/{period_id}"
    "/overrides/{override_id}/restore"
)
def restore_report_override(
    client_id: str,
    period_id: str,
    override_id: str,
    payload: dict,
):
    try:
        return json_response(
            report_editor.restore_override(
                client_id,
                period_id,
                override_id,
                payload.get("actor"),
            )
        )
    except ReportDataLockedError:
        raise
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/report-jobs")
def create_report_job(payload: dict):
    try:
        client_id = str(payload.get("client_id") or "").strip()
        period_id = str(payload.get("period_id") or "").strip()
        require_fields(
            {"client_id": client_id, "period_id": period_id},
            ["client_id", "period_id"],
        )
        job_options = {}
        report_type = str(payload.get("report_type") or payload.get("product") or "").strip()
        if report_type:
            job_options["report_type"] = report_type
        for key in ("report_model", "platform_scope", "objective"):
            if key in payload and payload.get(key) not in (None, ""):
                job_options[key] = str(payload.get(key)).strip()
        return json_response(
            report_jobs.create_job(
                client_id,
                period_id,
                dry_run=parse_bool(payload.get("dry_run")),
                **job_options,
            ),
            status_code=202,
        )
    except ActiveReportJobError as exc:
        return JSONResponse(
            content={
                "error": str(exc),
                "job": json_safe(exc.job),
            },
            status_code=409,
        )
    except ReportQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ReportTaskDispatchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/report-jobs/{job_id}")
def get_report_job(job_id: str):
    try:
        return json_response(report_jobs.get_job(job_id))
    except ReportJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/report-jobs")
def get_all_report_jobs(
    limit: int = 100,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    report_type: Optional[str] = None,
):
    try:
        filters = {"report_type": report_type} if report_type else {}
        if page is not None or page_size is not None:
            return json_response(
                report_jobs.all_history_page(
                    page=page or 1,
                    page_size=page_size or 20,
                    **filters,
                )
            )
        return json_response(
            report_jobs.all_history(limit=limit, **filters)
        )
    except ValueError as exc:
        raise bad_request(exc)


@app.get("/api/clients/{client_id}/report-jobs")
def get_client_report_jobs(
    client_id: str,
    limit: int = 100,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    report_type: Optional[str] = None,
):
    try:
        filters = {"report_type": report_type} if report_type else {}
        if page is not None or page_size is not None:
            return json_response(
                report_jobs.client_history_page(
                    client_id,
                    page=page or 1,
                    page_size=page_size or 20,
                    **filters,
                )
            )
        return json_response(
            report_jobs.client_history(
                client_id,
                limit=limit,
                **filters,
            )
        )
    except ValueError as exc:
        raise bad_request(exc)


@app.get(
    "/api/clients/{client_id}/report-periods/{period_id}/report-jobs"
)
def get_report_job_history(
    client_id: str,
    period_id: str,
    limit: int = 20,
):
    try:
        return json_response(
            report_jobs.history(client_id, period_id, limit=limit)
        )
    except ValueError as exc:
        raise bad_request(exc)


@app.post("/api/report-jobs/{job_id}/retry")
def retry_report_job(job_id: str):
    try:
        return json_response(
            report_jobs.retry_job(job_id),
            status_code=202,
        )
    except ActiveReportJobError as exc:
        return JSONResponse(
            content={
                "error": str(exc),
                "job": json_safe(exc.job),
            },
            status_code=409,
        )
    except ReportJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ReportJobTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ReportQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ReportTaskDispatchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/report-jobs/{job_id}/cancel")
def cancel_report_job(job_id: str, payload: Optional[dict] = None):
    try:
        body = payload or {}
        return json_response(
            report_jobs.cancel_job(
                job_id,
                reason=str(body.get("reason") or "").strip() or None,
            )
        )
    except ReportJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ReportJobTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/internal/report-jobs/{job_id}/execute")
async def execute_internal_report_job(job_id: str, request: Request):
    raw_body = await request.body()
    worker_base_url = str(
        os.getenv("REPORT_WORKER_BASE_URL") or ""
    ).strip().rstrip("/")
    worker_url = (
        f"{worker_base_url}{request.url.path}"
        if worker_base_url
        else str(request.url)
    )
    try:
        queue_backend = str(
            os.getenv("REPORT_QUEUE_BACKEND") or ""
        ).strip().lower()
        if queue_backend in {"qstash", "upstash", "upstash_qstash"}:
            verify_report_task_request(
                authorization=request.headers.get("Authorization"),
                qstash_signature=request.headers.get("Upstash-Signature"),
                body=raw_body,
                url=worker_url,
            )
        else:
            # Preserve the Cloud Tasks verification contract. The internal
            # endpoint is never used by the in-process local dispatcher.
            verify_cloud_tasks_oidc(request.headers.get("Authorization"))
    except ReportTaskAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    try:
        return json_response(
            await run_in_threadpool(report_job_worker.execute, job_id)
        )
    except ReportJobNotFoundError:
        # A task for a deleted job is a permanent no-op. A 2xx response stops
        # Stop the queue provider retrying an object that no longer exists.
        return json_response(
            {"job_id": job_id, "status": "ignored"},
        )
    except (ReportJobAlreadyRunningError, RetryableReportJobError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/clients/{client_id}/report-periods/{period_id}/edit-history"
)
def get_report_edit_history(client_id: str, period_id: str):
    try:
        return json_response(report_editor.history(client_id, period_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/image-proxy")
def image_proxy(url: str):
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
            timeout=8,
        )
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load image: {exc}")

    content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="URL did not return an image")
    if len(response.content) > 6_000_000:
        raise HTTPException(status_code=502, detail="Image is too large")
    return Response(
        content=response.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists() and os.getenv("DASHBOARD_API_ONLY", "").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("Dashboard frontend build not found. Run npm install and npm run build in dashboard first.")
    return FileResponse(index_path if index_path.exists() else DASHBOARD_DIR / "index.html")


@app.get("/{path:path}")
def spa_fallback(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = STATIC_DIR / path
    if "." in Path(path).name and candidate.exists():
        return FileResponse(candidate)
    return index()
