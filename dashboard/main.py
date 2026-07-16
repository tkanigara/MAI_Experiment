from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

try:
    from dashboard.config import DASHBOARD_DIR, STATIC_DIR
    from dashboard.repositories.dashboard_repository import (
        CSV_IMPORT_SLOTS,
        DashboardRepository,
        json_safe,
        parse_bool,
    )
    from dashboard.schemas import require_fields
    from dashboard.services.csv_import import import_report_csv
    from dashboard.services.kpi_service import upsert_kpi_target
    from dashboard.services.agentic_report import generate_agentic_report
except ModuleNotFoundError:
    from config import DASHBOARD_DIR, STATIC_DIR
    from repositories.dashboard_repository import (
        CSV_IMPORT_SLOTS,
        DashboardRepository,
        json_safe,
        parse_bool,
    )
    from schemas import require_fields
    from services.csv_import import import_report_csv
    from services.kpi_service import upsert_kpi_target
    from services.agentic_report import generate_agentic_report


repository = DashboardRepository()
app = FastAPI(title="MAI Social Media Dashboard API")


@app.exception_handler(HTTPException)
def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(content={"error": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(content={"error": str(exc)}, status_code=422)


def json_response(payload, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=json_safe(payload), status_code=status_code)


def bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def duplicate_client_message(exc: Exception) -> str:
    message = str(exc)
    if "duplicate key value" in message and "clients_client_code_key" in message:
        return "Client code already exists."
    return message


@app.get("/api/clients")
def get_clients():
    return json_response(repository.clients())


@app.post("/api/clients")
def create_client(payload: dict):
    try:
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
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
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
    account: Optional[UploadFile] = File(None),
    competitor: Optional[UploadFile] = File(None),
    competitor_content: Optional[UploadFile] = File(None),
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
        "ig_post": ig_post,
        "ig_story": ig_story,
        "fb_post": fb_post,
        "tt_post": tt_post,
        "yt_post": yt_post,
    }
    try:
        payload = {"client_id": client_id, "month_slug": month_slug}
        return json_response(import_report_csv(repository, payload, files), status_code=201)
    except ValueError as exc:
        raise bad_request(exc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for slot in CSV_IMPORT_SLOTS:
            file_item = files.get(slot)
            if file_item is not None:
                file_item.file.close()


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
        return json_response(
            generate_agentic_report(
                client_id=client_id,
                period_id=period_id,
                dry_run=parse_bool(payload.get("dry_run")),
            ),
            status_code=201,
        )
    except ValueError as exc:
        raise bad_request(exc)
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
