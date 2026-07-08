from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

try:
    from dashboard.config import BASE_DIR
except ModuleNotFoundError:
    from config import BASE_DIR


def database_url() -> str:
    load_dotenv(BASE_DIR / ".env")
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://mai_user:mai_password@localhost:55432/mai_socmed_report",
    )


def create_db_engine():
    return create_engine(database_url(), pool_pre_ping=True)
