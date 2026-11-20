from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.product_service import (
    ProductCategoryInactive,
    ProductCategoryNotFound,
    ProductNotFound,
    archive_product,
    create_product,
    get_product,
    list_products,
    update_product,
)


router = APIRouter(
    prefix="/products",
    tags=["Products"],
    dependencies=[Depends(require_super_admin)],
)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_endpoint(
    product_data: ProductCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return create_product(db, product_data, admin_id=actor.id)

    except ProductCategoryNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product category not found.",
        )

    except ProductCategoryInactive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Products cannot be assigned to an inactive category.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product could not be created. The SKU may already exist.",
        )


@router.get(
    "",
    response_model=list[ProductResponse],
)
def list_products_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    category_id: UUID | None = Query(default=None),
    product_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(DRAFT|ACTIVE|ARCHIVED)$",
    ),
    db: Session = Depends(get_db),
):
    return list_products(
        db,
        offset=offset,
        limit=limit,
        category_id=category_id,
        product_status=product_status,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
)
def get_product_endpoint(
    product_id: UUID,
    db: Session = Depends(get_db),
):
    product = get_product(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return product


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
)
def update_product_endpoint(
    product_id: UUID,
    product_data: ProductUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_product(db, product_id, product_data, admin_id=actor.id)

    except ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    except ProductCategoryNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product category not found.",
        )

    except ProductCategoryInactive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Products cannot be assigned to an inactive category.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product could not be updated. The SKU may already exist or a database constraint was violated.",
        )


@router.delete(
    "/{product_id}",
    response_model=ProductResponse,
)
def archive_product_endpoint(
    product_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return archive_product(db, product_id, admin_id=actor.id)

    except ProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product could not be archived.",
        )
