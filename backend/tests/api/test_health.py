
import pytest
from unittest.mock import Mock

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db


@pytest.mark.api
def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["application"]


@pytest.mark.api
def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.api
def test_health_endpoint_works_without_database(
    client,
    override_dependency,
):
    def failing_db():
        db = Mock()
        db.execute.side_effect = SQLAlchemyError(
            "Simulated database failure"
        )
        yield db

    override_dependency(get_db, failing_db)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.api
def test_readiness_returns_503_on_database_failure(
    client,
    override_dependency,
):
    def failing_db():
        db = Mock()
        db.execute.side_effect = SQLAlchemyError(
            "Sensitive simulated database error"
        )
        yield db

    override_dependency(get_db, failing_db)

    response = client.get("/ready")

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Database connection or PostGIS check failed"
    }

    assert "Sensitive simulated database error" not in response.text

