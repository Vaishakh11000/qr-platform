
# backend/app/main.py

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

app = FastAPI(
    title="QR Product Information Platform",
    description="Product management and QR engagement API",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "application": "QR Product Information Platform",
        "status": "running",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("""
                SELECT
                    current_database() AS database,
                    current_schema() AS schema,
                    version() AS postgres_version,
                    PostGIS_Full_Version() AS postgis_version
            """)
        ).mappings().one()

        return {
            "status": "healthy",
            "database": result["database"],
            "schema": result["schema"],
            "postgres": result["postgres_version"],
            "postgis": result["postgis_version"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from exc
