from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.services.category_service import (
    CategoryHierarchyCycle,
    CategoryNotFound,
    CategoryParentNotFound,
    create_category,
    deactivate_category,
    get_category,
    list_categories,
    update_category,
)


router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
    dependencies=[Depends(require_super_admin)],
)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category_endpoint(
    category_data: CategoryCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return create_category(db, category_data, admin_id=actor.id)

    except CategoryParentNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent category not found.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category could not be created because of a database constraint.",
        )


@router.get(
    "",
    response_model=list[CategoryResponse],
)
def list_categories_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_categories(
        db,
        offset=offset,
        limit=limit,
        is_active=is_active,
        parent_id=parent_id,
    )


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
)
def get_category_endpoint(
    category_id: UUID,
    db: Session = Depends(get_db),
):
    category = get_category(db, category_id)

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    return category


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
)
def update_category_endpoint(
    category_id: UUID,
    category_data: CategoryUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_category(db, category_id, category_data, admin_id=actor.id)

    except CategoryNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    except CategoryParentNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent category not found.",
        )

    except CategoryHierarchyCycle:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category hierarchy would contain a cycle.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category could not be updated because of a database constraint.",
        )


@router.delete(
    "/{category_id}",
    response_model=CategoryResponse,
)
def deactivate_category_endpoint(
    category_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return deactivate_category(db, category_id, admin_id=actor.id)

    except CategoryNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category could not be deactivated.",
        )
