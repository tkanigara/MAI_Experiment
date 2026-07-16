import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured.replace("postgresql+psycopg://", "postgresql://", 1)

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "15432")
    database = os.getenv("POSTGRES_DB", "mai_socmed_report")
    user = os.getenv("POSTGRES_USER", "mai_user")
    password = os.getenv("POSTGRES_PASSWORD", "mai_password")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

def get_connection():
    return psycopg.connect(database_url(), connect_timeout=10)
