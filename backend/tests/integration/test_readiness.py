
import pytest


@pytest.mark.integration
@pytest.mark.api
def test_readiness_endpoint(client):
    """
    Verify PostgreSQL and PostGIS availability
    using the dedicated test database.
    """
    response = client.get("/ready")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ready"
    assert data["database"] == "qr_platform_test"
    assert data["schema"] == "app"
    assert data["postgis"]
    