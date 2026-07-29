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


def _env_int(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    return value


def create_db_engine():
    return create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_size=_env_int("DB_POOL_SIZE", 3, 1),
        max_overflow=_env_int("DB_MAX_OVERFLOW", 2, 0),
        pool_timeout=_env_int("DB_POOL_TIMEOUT", 30, 1),
        pool_recycle=_env_int("DB_POOL_RECYCLE", 1800, 1),
        connect_args={
            "connect_timeout": _env_int("DB_CONNECT_TIMEOUT", 10, 1),
        },
    )
