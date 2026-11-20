from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.product_version import (
    ProductVersionCreate,
    ProductVersionResponse,
    ProductVersionUpdate,
)
from app.services.product_version_service import (
    VersionNotDraft,
    VersionNotFound,
    VersionProductArchived,
    VersionProductNotFound,
    VersionNotPublishable,
    create_product_version,
    get_product_version,
    list_product_versions,
    publish_product_version,
    update_product_version,
)


router = APIRouter(
    prefix="/products/{product_id}/versions",
    tags=["Product Versions"],
    dependencies=[Depends(require_super_admin)],
)


@router.post(
    "",
    response_model=ProductVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_version_endpoint(
    product_id: UUID,
    version_data: ProductVersionCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return create_product_version(db, product_id, version_data, admin_id=actor.id)

    except VersionProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    except VersionProductArchived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create versions for an archived product.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product version could not be created.",
        )


@router.get(
    "",
    response_model=list[ProductVersionResponse],
)
def list_product_versions_endpoint(
    product_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return list_product_versions(db, product_id)

    except VersionProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )


@router.get(
    "/{version_id}",
    response_model=ProductVersionResponse,
)
def get_product_version_endpoint(
    product_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
):
    version = get_product_version(db, product_id, version_id)

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product version not found.",
        )

    return version


@router.patch(
    "/{version_id}",
    response_model=ProductVersionResponse,
)
def update_product_version_endpoint(
    product_id: UUID,
    version_id: UUID,
    version_data: ProductVersionUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_product_version(
            db,
            product_id,
            version_id,
            version_data,
            admin_id=actor.id,
        )

    except VersionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product version not found.",
        )

    except VersionNotDraft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft versions can be edited.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product version could not be updated.",
        )


@router.post(
    "/{version_id}/publish",
    response_model=ProductVersionResponse,
)
def publish_product_version_endpoint(
    product_id: UUID,
    version_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return publish_product_version(
            db,
            product_id,
            version_id,
            admin_id=actor.id,
        )

    except VersionProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    except VersionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product version not found.",
        )

    except VersionProductArchived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot publish versions for an archived product.",
        )

    except VersionNotDraft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft versions can be published.",
        )

    except VersionNotPublishable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The current product version is inconsistent and cannot be replaced.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product version could not be published.",
        )
