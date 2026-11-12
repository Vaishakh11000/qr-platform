
# backend/app/core/config.py

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("POSTGRES_USER", "qr_app"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host="127.0.0.1",
    port=5432,
    database=os.getenv("POSTGRES_DB", "qr_platform"),
    query={"options": "-csearch_path=app,public"},
)

if not os.getenv("POSTGRES_PASSWORD"):
    raise RuntimeError("POSTGRES_PASSWORD is missing from project .env")

