from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
PLATFORM_TABLES = {
    "instagram": "instagram_reports",
    "facebook": "facebook_reports",
    "tiktok": "tiktok_reports",
    "youtube": "youtube_reports",
}
PLATFORM_KPI_METRICS = {
    "instagram": {"followers", "engagement", "reach"},
    "facebook": {"followers", "engagement", "reach"},
    "tiktok": {"followers", "engagement", "views"},
    "youtube": {"subscribers", "engagement", "views"},
}


def database_url() -> str:
    load_dotenv(BASE_DIR / ".env")
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://mai_user:mai_password@localhost:55432/mai_socmed_report",
    )


def json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    return value


def row_dict(row):
    return json_safe(dict(row)) if row else None


class DashboardRepository:
    def __init__(self):
        self.engine = create_engine(database_url(), pool_pre_ping=True)

    def clients(self):
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        c.id,
                        c.client_code,
                        c.client_name,
                        c.industry,
                        c.has_instagram,
                        c.has_facebook,
                        c.has_tiktok,
                        c.has_youtube,
                        COUNT(p.id) FILTER (WHERE p.is_active) AS connected_profiles
                    FROM clients c
                    LEFT JOIN client_social_profiles p ON p.client_id = c.id
                    WHERE c.is_active
                    GROUP BY c.id
                    ORDER BY c.client_name
                    """
                )
            ).mappings()
            return [row_dict(row) for row in rows]

    def platforms(self, client_id: str):
        with self.engine.begin() as conn:
            client = conn.execute(
                text(
                    """
                    SELECT id, client_code, client_name, industry,
                           has_instagram, has_facebook, has_tiktok, has_youtube
                    FROM clients
                    WHERE id = :client_id
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            profiles = conn.execute(
                text(
                    """
                    SELECT id, platform, profile_name, profile_url, image_url, source_profile_id
                    FROM client_social_profiles
                    WHERE client_id = :client_id AND is_active
                    ORDER BY platform, profile_name
                    """
                ),
                {"client_id": client_id},
            ).mappings()
            return {"client": row_dict(client), "profiles": [row_dict(row) for row in profiles]}

    def overview(self, client_id: str, platform: str):
        if platform not in PLATFORM_TABLES:
            raise ValueError("Unsupported platform")
        table = PLATFORM_TABLES[platform]
        with self.engine.begin() as conn:
            report = conn.execute(
                text(
                    f"""
                    SELECT
                        r.*,
                        rp.period_label,
                        rp.period_start,
                        rp.period_end,
                        p.profile_name,
                        p.profile_url,
                        p.image_url
                    FROM {table} r
                    JOIN report_periods rp ON rp.id = r.report_period_id
                    LEFT JOIN client_social_profiles p ON p.id = r.profile_id
                    WHERE r.client_id = :client_id
                    ORDER BY rp.period_end DESC
                    LIMIT 1
                    """
                ),
                {"client_id": client_id},
            ).mappings().first()
            report_data = row_dict(report)
            period_id = report_data["report_period_id"] if report_data else None
            kpi_results = []
            if period_id:
                kpi_results = [
                    row_dict(row)
                    for row in conn.execute(
                        text(
                            """
                            SELECT metric_name, actual_month, actual_year, target_month,
                                   target_year, achievement_month, achievement_year, unit
                            FROM kpi_results
                            WHERE client_id = :client_id
                              AND platform = :platform
                              AND report_period_id = :period_id
                            ORDER BY metric_name
                            """
                        ),
                        {
                            "client_id": client_id,
                            "platform": platform,
                            "period_id": period_id,
                        },
                    ).mappings()
                ]
            kpi_targets = [
                row_dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT id, metric_name, period_year, target_month,
                               target_year, unit, notes, updated_at
                        FROM kpi_targets
                        WHERE client_id = :client_id AND platform = :platform
                        ORDER BY period_year DESC, metric_name
                        """
                    ),
                    {"client_id": client_id, "platform": platform},
                ).mappings()
            ]
        return {
            "platform": platform,
            "report": report_data,
            "metrics": overview_metrics(platform, report_data),
            "kpi_results": kpi_results,
            "kpi_targets": kpi_targets,
            "top_posts": (report_data or {}).get("top_posts") or [],
            "low_posts": (report_data or {}).get("low_posts") or [],
        }

    def upsert_kpi_target(self, payload: dict):
        required = ["client_id", "platform", "metric_name", "period_year"]
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")
        platform = payload["platform"]
        metric_name = payload["metric_name"].strip().lower().replace(" ", "_")
        if platform not in PLATFORM_TABLES:
            raise ValueError("Unsupported platform")
        if metric_name not in PLATFORM_KPI_METRICS[platform]:
            allowed = ", ".join(sorted(PLATFORM_KPI_METRICS[platform]))
            raise ValueError(f"Unsupported KPI metric for {platform}. Use: {allowed}")
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO kpi_targets (
                        client_id, platform, metric_name, period_year,
                        target_month, target_year, unit, notes, created_by
                    )
                    VALUES (
                        :client_id, :platform, :metric_name, :period_year,
                        :target_month, :target_year, :unit, :notes, :created_by
                    )
                    ON CONFLICT (client_id, platform, metric_name, period_year)
                    DO UPDATE SET
                        target_month = EXCLUDED.target_month,
                        target_year = EXCLUDED.target_year,
                        unit = EXCLUDED.unit,
                        notes = EXCLUDED.notes,
                        updated_at = now()
                    RETURNING id, metric_name, period_year, target_month,
                              target_year, unit, notes, updated_at
                    """
                ),
                {
                    "client_id": payload["client_id"],
                    "platform": platform,
                    "metric_name": metric_name,
                    "period_year": int(payload["period_year"]),
                    "target_month": payload.get("target_month") or None,
                    "target_year": payload.get("target_year") or None,
                    "unit": payload.get("unit") or None,
                    "notes": payload.get("notes") or None,
                    "created_by": payload.get("created_by") or "dashboard",
                },
            ).mappings().one()
            synced = self.sync_kpi_results(conn, payload, row["id"], metric_name)
            result = row_dict(row)
            result["synced_results"] = synced
            return result

    def sync_kpi_results(self, conn, payload: dict, target_id, metric_name: str) -> int:
        result = conn.execute(
            text(
                """
                UPDATE kpi_results kr
                SET
                    kpi_target_id = :target_id,
                    target_month = CAST(:target_month AS NUMERIC),
                    target_year = CAST(:target_year AS NUMERIC),
                    unit = COALESCE(:unit, kr.unit),
                    achievement_month = CASE
                        WHEN CAST(:target_month AS NUMERIC) IS NOT NULL
                         AND CAST(:target_month AS NUMERIC) <> 0
                         AND kr.actual_month IS NOT NULL
                        THEN ROUND((kr.actual_month / CAST(:target_month AS NUMERIC)) * 100, 2)
                        ELSE NULL
                    END,
                    achievement_year = CASE
                        WHEN CAST(:target_year AS NUMERIC) IS NOT NULL
                         AND CAST(:target_year AS NUMERIC) <> 0
                         AND kr.actual_year IS NOT NULL
                        THEN ROUND((kr.actual_year / CAST(:target_year AS NUMERIC)) * 100, 2)
                        ELSE NULL
                    END,
                    updated_at = now()
                FROM report_periods rp
                WHERE kr.report_period_id = rp.id
                  AND kr.client_id = :client_id
                  AND kr.platform = :platform
                  AND kr.metric_name = :metric_name
                  AND EXTRACT(YEAR FROM rp.period_start) = :period_year
                """
            ),
            {
                "target_id": target_id,
                "client_id": payload["client_id"],
                "platform": payload["platform"],
                "metric_name": metric_name,
                "period_year": int(payload["period_year"]),
                "target_month": payload.get("target_month") or None,
                "target_year": payload.get("target_year") or None,
                "unit": payload.get("unit") or None,
            },
        )
        return result.rowcount


def overview_metrics(platform: str, report: dict | None):
    if not report:
        return []
    if platform == "youtube":
        return [
            metric("Subscribers", report.get("total_subscribers")),
            metric("Growth Rate", report.get("subscriber_growth_rate"), "%"),
            metric("Views", report.get("total_views")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    if platform == "tiktok":
        return [
            metric("Followers", report.get("total_followers")),
            metric("Growth Rate", report.get("follower_growth_rate"), "%"),
            metric("Views", report.get("total_views")),
            metric("Engagement", report.get("total_engagement")),
            metric("Eng. Rate", report.get("engagement_rate"), "%"),
            metric("Posts", report.get("total_posts")),
        ]
    return [
        metric("Followers", report.get("total_followers")),
        metric("Growth Rate", report.get("follower_growth_rate"), "%"),
        metric("Reach", report.get("reach")),
        metric("Engagement", report.get("total_engagement")),
        metric("Eng. Rate", report.get("engagement_rate"), "%"),
        metric("Posts", report.get("total_posts")),
    ]


def metric(label: str, value, suffix: str = ""):
    return {"label": label, "value": value, "suffix": suffix}


class DashboardHandler(SimpleHTTPRequestHandler):
    repository = DashboardRepository()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/clients":
            self.send_json(self.repository.clients())
            return
        if parsed.path.startswith("/api/clients/"):
            parts = [part for part in parsed.path.split("/") if part]
            try:
                if len(parts) == 4 and parts[1] == "clients" and parts[3] == "platforms":
                    self.send_json(self.repository.platforms(parts[2]))
                    return
                if (
                    len(parts) == 6
                    and parts[1] == "clients"
                    and parts[3] == "platforms"
                    and parts[5] == "overview"
                ):
                    self.send_json(self.repository.overview(parts[2], parts[4]))
                    return
            except ValueError as exc:
                self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
                return
        if parsed.path == "/":
            self.path = "/index.html"
        elif not parsed.path.startswith("/api/") and "." not in Path(parsed.path).name:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/kpi-targets":
            self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            self.send_json(self.repository.upsert_kpi_target(payload), HTTPStatus.CREATED)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)

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
    query = parse_qs(urlparse(os.environ.get("DASHBOARD_QUERY", "")).query)
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT") or query.get("port", [8000])[0])
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
