from __future__ import annotations

import cgi
import json
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

try:
    from dashboard.config import STATIC_DIR  # noqa: E402
    from dashboard.repositories.dashboard_repository import (  # noqa: E402
        DashboardRepository,
        json_safe,
    )
    from dashboard.repositories.meta_ads_repository import MetaAdsRepository  # noqa: E402
    from dashboard.routes import clients, images, imports, kpi, reports  # noqa: E402
except ModuleNotFoundError:
    from config import STATIC_DIR  # noqa: E402
    from repositories.dashboard_repository import (  # noqa: E402
        DashboardRepository,
        json_safe,
    )
    from repositories.meta_ads_repository import MetaAdsRepository  # noqa: E402
    from routes import clients, images, imports, kpi, reports  # noqa: E402


class DashboardHandler(SimpleHTTPRequestHandler):
    repository = DashboardRepository()
    meta_ads_repository = MetaAdsRepository(repository.engine)

    def __init__(self, *args, **kwargs):
        static_directory = STATIC_DIR if STATIC_DIR.exists() else DASHBOARD_DIR
        super().__init__(*args, directory=str(static_directory), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if images.handle_get(self, parsed):
            return
        if clients.handle_get(self, parts, parsed):
            return
        if parsed.path == "/":
            self.path = "/index.html"
        elif not parsed.path.startswith("/api/") and "." not in Path(parsed.path).name:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        for route in (clients, imports, reports, kpi):
            if route.handle_post(self, parsed if route in (imports, reports, kpi) else parts):
                return
        self.send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if clients.handle_put(self, parts):
            return
        self.send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if clients.handle_delete(self, parts):
            return
        self.send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def parse_multipart(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            raise ValueError("Expected multipart/form-data")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        fields = {}
        for key in form.keys():
            item = form[key]
            if isinstance(item, list):
                item = item[0]
            fields[key] = item if getattr(item, "filename", None) else item.value
        return fields

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(json_safe(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status=HTTPStatus.INTERNAL_SERVER_ERROR):
        self.send_json({"error": message}, status)


def main():
    api_only = os.getenv("DASHBOARD_API_ONLY", "").lower() in {"1", "true", "yes"}
    if not STATIC_DIR.exists() and not api_only:
        raise RuntimeError(
            "Dashboard frontend build not found. Run `npm install` and `npm run build` in the dashboard folder first."
        )
    query = parse_qs(urlparse(os.environ.get("DASHBOARD_QUERY", "")).query)
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("PORT") or os.getenv("DASHBOARD_PORT") or query.get("port", [8000])[0])
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
