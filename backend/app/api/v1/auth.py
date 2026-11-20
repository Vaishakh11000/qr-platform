from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.models import AdminUser, Role
from app.schemas.admin_auth import (
    AdminIdentityResponse,
    AdminLoginRequest,
    AdminLoginResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=AdminLoginResponse,
)
def admin_login(
    credentials: AdminLoginRequest,
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(AdminUser, Role.name)
        .join(Role, Role.id == AdminUser.role_id)
        .where(AdminUser.email == credentials.email)
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    admin, role_name = result

    if not admin.is_active or not verify_password(
        credentials.password,
        admin.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return AdminLoginResponse(
        access_token=create_access_token(admin.id),
        expires_in=settings.admin_access_token_expire_minutes * 60,
        admin_id=admin.id,
        name=admin.name,
        email=admin.email,
        role=role_name,
    )


@router.get(
    "/me",
    response_model=AdminIdentityResponse,
)
def get_admin_identity(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    role_name = db.scalar(
        select(Role.name).where(Role.id == admin.role_id)
    )

    return AdminIdentityResponse(
        id=admin.id,
        name=admin.name,
        email=admin.email,
        role=role_name,
    )
