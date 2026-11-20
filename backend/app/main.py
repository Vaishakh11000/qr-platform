# backend/app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from app.api.v1.router import api_router
from app.api.public_scan_page import router as public_scan_page_router

@asynccontextmanager

async def lifespan(app: FastAPI):
    yield

    if getattr(app.state, "dispose_engine_on_shutdown", True):
        engine.dispose()

app = FastAPI(
    title=settings.app_name,
    description="Product management and QR engagement API",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(public_scan_page_router)

@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "status": "running",
    }


@app.get("/health")
def health():
    """Check whether the API process is running."""
    return {
        "status": "healthy",
        "application": settings.app_name,
    }


@app.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Check whether required database services are available."""
    try:
        result = db.execute(
            text("""
                SELECT
                    current_database() AS database,
                    current_schema() AS schema,
                    PostGIS_Lib_Version() AS postgis_version
            """)
        ).mappings().one()

        return {
            "status": "ready",
            "database": result["database"],
            "schema": result["schema"],
            "postgis": result["postgis_version"],
        }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection or PostGIS check failed",
        ) from exc
