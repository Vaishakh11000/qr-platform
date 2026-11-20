from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import AdminUser, Role


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    admin_id = decode_access_token(credentials.credentials)

    if admin_id is None:
        raise unauthorized

    admin = db.get(AdminUser, admin_id)

    if admin is None or not admin.is_active:
        raise unauthorized

    return admin


def require_super_admin(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminUser:
    role_name = db.scalar(
        select(Role.name).where(Role.id == admin.role_id)
    )

    if role_name != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUPER_ADMIN role required.",
        )

    return admin
