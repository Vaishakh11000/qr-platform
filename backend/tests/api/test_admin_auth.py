from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.core.auth import get_current_admin, require_super_admin
from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.models import AdminUser, Role
from fastapi.security import HTTPAuthorizationCredentials


def create_admin(db, role_name="SUPER_ADMIN", active=True):
    role = Role(
        name=f"{role_name}-{uuid4().hex[:8]}",
        description="Authentication test role",
    )
    db.add(role)
    db.flush()

    admin = AdminUser(
        name="Authentication Test Admin",
        email=f"{uuid4().hex}@example.test",
        password_hash=hash_password("Test-Password-123!"),
        role_id=role.id,
        is_active=active,
    )
    db.add(admin)
    db.flush()

    return admin, role


def test_login_success(client, db_session):
    admin, role = create_admin(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": admin.email,
            "password": "Test-Password-123!",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["token_type"] == "bearer"
    assert data["role"] == role.name
    assert data["admin_id"] == str(admin.id)
    assert data["expires_in"] == 1800
    assert data["access_token"]

    db_session.refresh(admin)
    assert admin.last_login_at is not None


def test_login_rejects_wrong_password(client, db_session):
    admin, _ = create_admin(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": admin.email,
            "password": "Wrong-Password",
        },
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.test",
            "password": "Test-Password-123!",
        },
    )

    assert response.status_code == 401


def test_login_rejects_inactive_admin(client, db_session):
    admin, _ = create_admin(db_session, active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": admin.email,
            "password": "Test-Password-123!",
        },
    )

    assert response.status_code == 401


def test_me_rejects_missing_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.parametrize("token", ["invalid-token", ""])
def test_me_rejects_malformed_token(client, token):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_me_accepts_valid_token(client, db_session):
    admin, role = create_admin(db_session)
    token = create_access_token(admin.id)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(admin.id)
    assert response.json()["role"] == role.name


def test_me_rejects_expired_token(client, db_session):
    admin, _ = create_admin(db_session)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(admin.id),
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "type": "access",
        },
        settings.admin_token_secret.get_secret_value(),
        algorithm="HS256",
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_me_rejects_deactivated_admin(client, db_session):
    admin, _ = create_admin(db_session)
    token = create_access_token(admin.id)

    admin.is_active = False
    db_session.flush()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_super_admin_dependency_rejects_other_role(db_session):
    admin, _ = create_admin(db_session, role_name="CONTENT_EDITOR")

    with pytest.raises(HTTPException) as exc:
        require_super_admin(admin=admin, db=db_session)

    assert exc.value.status_code == 403


def test_super_admin_dependency_accepts_super_admin(db_session):
    admin, _ = create_admin(db_session)

    # Use the exact role name required by the authorization dependency.
    admin_role = db_session.query(Role).filter(
        Role.id == admin.role_id
    ).one()
    admin_role.name = "SUPER_ADMIN"
    db_session.flush()

    result = require_super_admin(admin=admin, db=db_session)

    assert result.id == admin.id


def test_current_admin_rejects_unknown_admin(db_session):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(uuid4()),
    )

    with pytest.raises(HTTPException) as exc:
        get_current_admin(credentials=credentials, db=db_session)

    assert exc.value.status_code == 401
