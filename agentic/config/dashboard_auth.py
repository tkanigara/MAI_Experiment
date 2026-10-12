"""Backend-only authentication for read-only dashboard retrieval."""

import os
from urllib.parse import urlsplit


def dashboard_read_headers(base_url: str) -> dict[str, str]:
    token = str(os.getenv("DASHBOARD_RETRIEVAL_TOKEN") or "").strip()
    if not token:
        return {}
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("Dashboard retrieval authentication requires HTTPS or loopback HTTP.")
    return {"Authorization": f"Bearer {token}"}
