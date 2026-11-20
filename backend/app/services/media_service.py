from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Product, ProductMedia, ProductVersion
from app.services.media_storage import StoredMedia
from app.services.audit_service import record_audit_event


DEFAULT_STORAGE_ROOT = settings.media_storage_root


class MediaProductNotFound(Exception):
    pass


class MediaProductArchived(Exception):
    pass


class MediaVersionNotFound(Exception):
    pass


class MediaVersionNotDraft(Exception):
    pass


class MediaNotFound(Exception):
    pass


def resolve_storage_path(
    storage_key: str,
    storage_root: Path | None = None,
) -> Path:
    """
    Resolve a storage key safely inside the configured storage directory.
    """

    root = Path(storage_root or DEFAULT_STORAGE_ROOT).resolve()
    file_path = (root / storage_key).resolve()

    try:
        file_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid storage key.") from exc

    if not storage_key or Path(storage_key).is_absolute():
        raise ValueError("Invalid storage key.")

    return file_path


def create_product_media(
    db: Session,
    product_id: UUID,
    media_type: str,
    stored_media: StoredMedia,
    *,
    version_id: UUID | None = None,
    display_order: int = 0,
    alt_text: str | None = None,
    admin_id: UUID | None = None,
) -> ProductMedia:
    """
    Register an already stored file in the product_media table.
    """

    product = db.get(Product, product_id)

    if product is None:
        raise MediaProductNotFound()

    if product.status == "ARCHIVED":
        raise MediaProductArchived()

    if version_id is not None:
        version = db.scalar(
            select(ProductVersion).where(
                ProductVersion.id == version_id,
                ProductVersion.product_id == product_id,
            )
        )

        if version is None:
            raise MediaVersionNotFound()

        if version.status != "DRAFT":
            raise MediaVersionNotDraft()

    media = ProductMedia(
        product_id=product_id,
        version_id=version_id,
        media_type=media_type,
        storage_key=stored_media.storage_key,
        original_filename=stored_media.original_filename,
        mime_type=stored_media.mime_type,
        file_size_bytes=stored_media.file_size_bytes,
        checksum_sha256=stored_media.checksum_sha256,
        display_order=display_order,
        alt_text=alt_text,
    )

    db.add(media)

    try:
        db.flush()
        record_audit_event(
            db,
            admin_id=admin_id,
            action="PRODUCT_MEDIA_UPLOADED",
            entity_type="PRODUCT_MEDIA",
            entity_id=media.id,
            new_values={
                "product_id": str(product_id),
                "version_id": str(version_id) if version_id else None,
                "media_type": media.media_type,
                "original_filename": media.original_filename,
                "mime_type": media.mime_type,
                "file_size_bytes": media.file_size_bytes,
                "checksum_sha256": media.checksum_sha256,
            },
        )
        db.commit()
        db.refresh(media)
    except IntegrityError:
        db.rollback()
        raise

    return media


def list_product_media(
    db: Session,
    product_id: UUID,
    *,
    version_id: UUID | None = None,
) -> list[ProductMedia]:
    """
    List media belonging to a product.

    When version_id is provided, only media attached to that version
    is returned.
    """

    product = db.get(Product, product_id)

    if product is None:
        raise MediaProductNotFound()

    query = select(ProductMedia).where(
        ProductMedia.product_id == product_id
    )

    if version_id is not None:
        query = query.where(
            ProductMedia.version_id == version_id
        )

    query = query.order_by(
        ProductMedia.display_order,
        ProductMedia.created_at,
        ProductMedia.id,
    )

    return list(db.scalars(query).all())


def get_product_media(
    db: Session,
    product_id: UUID,
    media_id: UUID,
) -> ProductMedia | None:
    """
    Retrieve a media record belonging to a specific product.
    """

    return db.scalar(
        select(ProductMedia).where(
            ProductMedia.id == media_id,
            ProductMedia.product_id == product_id,
        )
    )


def delete_product_media(
    db: Session,
    product_id: UUID,
    media_id: UUID,
    storage_root: Path | None = None,
    admin_id: UUID | None = None,
) -> ProductMedia:
    """
    Delete a media record and then remove its stored file.
    """

    media = get_product_media(db, product_id, media_id)

    if media is None:
        raise MediaNotFound()

    file_path = resolve_storage_path(
        media.storage_key,
        storage_root,
    )

    snapshot = {
        "product_id": str(media.product_id),
        "version_id": str(media.version_id) if media.version_id else None,
        "media_type": media.media_type,
        "original_filename": media.original_filename,
        "mime_type": media.mime_type,
        "file_size_bytes": media.file_size_bytes,
        "checksum_sha256": media.checksum_sha256,
    }

    db.delete(media)

    try:
        record_audit_event(
            db,
            admin_id=admin_id,
            action="PRODUCT_MEDIA_DELETED",
            entity_type="PRODUCT_MEDIA",
            entity_id=media.id,
            old_values=snapshot,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    file_path.unlink(missing_ok=True)

    return media
