from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models import AdminUser, Role
from app.schemas.administration import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserStatusUpdate,
    PlatformSettingsUpdate,
)
from app.services.audit_service import record_audit_event
from app.services.system_setting_service import get_public_base_url


router = APIRouter(
    prefix="/admin/users",
    tags=["Administration"],
    dependencies=[Depends(require_super_admin)],
)


@router.get("", response_model=list[AdminUserResponse])
def list_admin_users(db: Session = Depends(get_db)):
    rows = db.execute(
        select(AdminUser, Role.name).join(Role, Role.id == AdminUser.role_id)
        .order_by(AdminUser.created_at, AdminUser.id)
    ).all()
    return [
        AdminUserResponse(
            id=admin.id,
            name=admin.name,
            email=admin.email,
            role=role,
            is_active=admin.is_active,
            last_login_at=admin.last_login_at,
            created_at=admin.created_at,
        )
        for admin, role in rows
    ]


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    data: AdminUserCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    role = db.scalar(select(Role).where(Role.name == "SUPER_ADMIN"))
    if role is None:
        raise HTTPException(status_code=409, detail="The SUPER_ADMIN role is not configured.")

    admin = AdminUser(
        name=data.name,
        email=str(data.email).lower(),
        password_hash=hash_password(data.password),
        role_id=role.id,
        is_active=True,
    )
    db.add(admin)
    try:
        db.flush()
        record_audit_event(
            db,
            admin_id=actor.id,
            action="ADMIN_CREATED",
            entity_type="ADMIN_USER",
            entity_id=admin.id,
            new_values={"name": admin.name, "email": admin.email, "role": role.name, "is_active": True},
        )
        db.commit()
        db.refresh(admin)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An administrator with this email already exists.") from exc

    return AdminUserResponse(
        id=admin.id,
        name=admin.name,
        email=admin.email,
        role=role.name,
        is_active=admin.is_active,
        last_login_at=admin.last_login_at,
        created_at=admin.created_at,
    )


@router.patch("/{admin_id}", response_model=AdminUserResponse)
def update_admin_user_status(
    admin_id: UUID,
    data: AdminUserStatusUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administrator not found.")
    if admin.id == actor.id and not data.is_active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")

    role = db.scalar(select(Role).where(Role.id == admin.role_id).with_for_update())
    role_name = role.name if role is not None else "UNKNOWN"
    if admin.is_active and not data.is_active and role_name == "SUPER_ADMIN":
        active_admin_count = db.scalar(
            select(func.count(AdminUser.id))
            .join(Role, Role.id == AdminUser.role_id)
            .where(AdminUser.is_active.is_(True), Role.name == "SUPER_ADMIN")
        ) or 0
        if active_admin_count <= 1:
            raise HTTPException(status_code=409, detail="The last active super administrator cannot be deactivated.")

    old_active = admin.is_active
    admin.is_active = data.is_active
    record_audit_event(
        db,
        admin_id=actor.id,
        action="ADMIN_ACTIVATED" if data.is_active else "ADMIN_DEACTIVATED",
        entity_type="ADMIN_USER",
        entity_id=admin.id,
        old_values={"is_active": old_active},
        new_values={"is_active": admin.is_active, "email": admin.email},
    )
    db.commit()
    db.refresh(admin)
    return AdminUserResponse(
        id=admin.id,
        name=admin.name,
        email=admin.email,
        role=role_name,
        is_active=admin.is_active,
        last_login_at=admin.last_login_at,
        created_at=admin.created_at,
    )


settings_router = APIRouter(
    prefix="/settings",
    tags=["Administration"],
    dependencies=[Depends(require_super_admin)],
)


@settings_router.get("", response_model=dict[str, str])
def read_platform_settings(db: Session = Depends(get_db)):
    return {"public_base_url": get_public_base_url(db)}


@settings_router.put("", response_model=dict[str, str])
def update_platform_settings(
    data: PlatformSettingsUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.models import SystemSetting
    setting = db.scalar(
        select(SystemSetting).where(SystemSetting.setting_key == "public_base_url")
    )
    old_value = get_public_base_url(db)
    if setting is None:
        setting = SystemSetting(setting_key="public_base_url", setting_value=data.public_base_url, updated_by=actor.id)
        db.add(setting)
    else:
        setting.setting_value = data.public_base_url
        setting.updated_by = actor.id
    db.flush()
    record_audit_event(
        db,
        admin_id=actor.id,
        action="PLATFORM_SETTING_UPDATED",
        entity_type="SYSTEM_SETTING",
        entity_id=setting.id,
        old_values={"public_base_url": old_value},
        new_values={"public_base_url": data.public_base_url},
    )
    db.commit()
    return {"public_base_url": data.public_base_url}
