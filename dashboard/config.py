from __future__ import annotations

from pathlib import Path


DASHBOARD_DIR = Path(__file__).resolve().parent
BASE_DIR = DASHBOARD_DIR.parent
STATIC_DIR = DASHBOARD_DIR / "dist"
