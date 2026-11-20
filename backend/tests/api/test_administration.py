from app.models import AuditLog
from app.services.qr_service import get_qr_destination


def test_administration_endpoints_require_authentication(client):
    assert client.get("/api/v1/admin/users").status_code == 401
    assert client.get("/api/v1/settings").status_code == 401


def test_create_admin_user_records_audit_event(admin_client, db_session):
    response = admin_client.post(
        "/api/v1/admin/users",
        json={
            "name": "New Operator",
            "email": "Operator@Example.test",
            "password": "Temporary-Password-123",
        },
    )

    assert response.status_code == 201
    user = response.json()
    assert user["email"] == "operator@example.test"
    assert user["role"] == "SUPER_ADMIN"
    assert user["is_active"] is True
    assert "password" not in user

    audit = db_session.query(AuditLog).filter_by(
        action="ADMIN_CREATED",
        entity_id=user["id"],
    ).one()
    assert audit.new_values["email"] == "operator@example.test"


def test_admin_cannot_deactivate_self(admin_client):
    admin_id = admin_client.get("/api/v1/auth/me").json()["id"]
    response = admin_client.patch(
        f"/api/v1/admin/users/{admin_id}",
        json={"is_active": False},
    )
    assert response.status_code == 409


def test_public_base_url_setting_updates_qr_destinations(admin_client, db_session):
    response = admin_client.put(
        "/api/v1/settings",
        json={"public_base_url": "https://products.example.test"},
    )

    assert response.status_code == 200
    assert response.json() == {"public_base_url": "https://products.example.test"}
    assert get_qr_destination("example-token", db_session) == (
        "https://products.example.test/q/example-token"
    )

    audit_rows = admin_client.get("/api/v1/audit-logs?action=PLATFORM_SETTING_UPDATED")
    assert audit_rows.status_code == 200
    assert audit_rows.json()["total"] == 1


def test_public_base_url_rejects_non_http_urls(admin_client):
    response = admin_client.put(
        "/api/v1/settings",
        json={"public_base_url": "javascript:alert(1)"},
    )
    assert response.status_code == 422
