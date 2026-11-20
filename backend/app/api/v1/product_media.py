import logging

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.product_media import ProductMediaResponse
from app.services.media_storage import (
    InvalidMediaFile,
    UnsupportedMediaType,
    UploadTooLarge,
    store_upload,
)
from app.services.media_service import (
    MediaNotFound,
    MediaProductArchived,
    MediaProductNotFound,
    MediaVersionNotDraft,
    MediaVersionNotFound,
    create_product_media,
    delete_product_media,
    get_product_media,
    list_product_media,
    resolve_storage_path,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/products/{product_id}/media",
    tags=["Product Media"],
    dependencies=[Depends(require_super_admin)],
)


def remove_uploaded_file(storage_key: str) -> None:
    path = resolve_storage_path(storage_key)
    path.unlink(missing_ok=True)


@router.post(
    "",
    response_model=ProductMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_media_endpoint(
    product_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    file: UploadFile = File(...),
    media_type: str = Form(...),
    version_id: UUID | None = Form(default=None),
    display_order: int = Form(default=0, ge=0),
    alt_text: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    stored_media = None
    registered = False

    try:
        stored_media = await store_upload(
            file,
            media_type,
        )

        media = create_product_media(
            db,
            product_id,
            media_type.upper(),
            stored_media,
            version_id=version_id,
            display_order=display_order,
            alt_text=alt_text,
            admin_id=actor.id,
        )

        registered = True
        return media

    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    except (InvalidMediaFile, UnsupportedMediaType) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except MediaProductNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        ) from exc

    except MediaProductArchived as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot upload media to an archived product.",
        ) from exc

    except MediaVersionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product version not found for this product.",
        ) from exc

    except MediaVersionNotDraft as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Media can only be attached to draft versions.",
        ) from exc

    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Media metadata could not be saved.",
        ) from exc

    finally:
        if stored_media is not None and not registered:
            try:
                remove_uploaded_file(stored_media.storage_key)
            except (OSError, ValueError):
                logger.exception(
                    "Failed to clean up unregistered media file: %s",
                    stored_media.storage_key,
                )

        await file.close()


@router.get(
    "",
    response_model=list[ProductMediaResponse],
)
def list_product_media_endpoint(
    product_id: UUID,
    version_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    try:
        return list_product_media(
            db,
            product_id,
            version_id=version_id,
        )

    except MediaProductNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )


@router.get("/{media_id}/file")
def download_product_media_endpoint(
    product_id: UUID,
    media_id: UUID,
    db: Session = Depends(get_db),
):
    media = get_product_media(db, product_id, media_id)

    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product media not found.",
        )

    try:
        file_path = resolve_storage_path(media.storage_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid media storage reference.",
        ) from exc

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored media file not found.",
        )

    return FileResponse(
        path=file_path,
        media_type=media.mime_type,
        filename=media.original_filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/{media_id}",
    response_model=ProductMediaResponse,
)
def get_product_media_endpoint(
    product_id: UUID,
    media_id: UUID,
    db: Session = Depends(get_db),
):
    media = get_product_media(db, product_id, media_id)

    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product media not found.",
        )

    return media


@router.delete(
    "/{media_id}",
    response_model=ProductMediaResponse,
)
def delete_product_media_endpoint(
    product_id: UUID,
    media_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return delete_product_media(
            db,
            product_id,
            media_id,
            admin_id=actor.id,
        )

    except MediaNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product media not found.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product media could not be deleted.",
        )
