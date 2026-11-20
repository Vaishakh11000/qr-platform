import pytest

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.models import (
    Product,
    ProductCategory,
    ProductVersion,
    ProductMedia,
)

def create_test_product(db_session, suffix):
    """Create a product and its category for integrity tests."""

    category = ProductCategory(
        name=f"Test Category {suffix}",
    )
    db_session.add(category)
    db_session.flush()

    product = Product(
        sku=f"TEST-PRODUCT-{suffix}",
        name=f"Test Product {suffix}",
        category_id=category.id,
    )
    db_session.add(product)
    db_session.flush()

    return product, category


def create_test_version(db_session, product, version_number=1):
    """Create a valid draft product version."""

    version = ProductVersion(
        product_id=product.id,
        version_number=version_number,
        content_snapshot={"description": "Test product content"},
        status="DRAFT",
    )
    db_session.add(version)
    db_session.flush()

    return version


@pytest.mark.integration
def test_product_rejects_invalid_status(db_session):
    product, _ = create_test_product(db_session, "INVALID-STATUS")

    product.status = "INVALID"

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_sku_must_be_unique(db_session):
    product, category = create_test_product(db_session, "DUPLICATE-SKU")

    duplicate = Product(
        sku=product.sku,
        name="Duplicate Product",
        category_id=category.id,
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_category_cannot_be_its_own_parent(db_session):
    category = ProductCategory(
        name="Self Parent Category",
    )

    db_session.add(category)
    db_session.flush()

    category.parent_id = category.id

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_version_number_must_be_positive(db_session):
    product, _ = create_test_product(db_session, "INVALID-VERSION")

    version = ProductVersion(
        product_id=product.id,
        version_number=0,
        content_snapshot={"description": "Invalid version"},
    )

    db_session.add(version)

    with pytest.raises(IntegrityError):
        db_session.flush()

@pytest.mark.integration
def test_product_version_number_must_be_unique_per_product(db_session):
    product, _ = create_test_product(db_session, "DUPLICATE-VERSION")

    create_test_version(db_session, product, version_number=1)

    duplicate = ProductVersion(
        product_id=product.id,
        version_number=1,
        content_snapshot={"description": "Duplicate version"},
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_version_rejects_invalid_status(db_session):
    product, _ = create_test_product(db_session, "INVALID-VERSION-STATUS")

    version = create_test_version(db_session, product)

    version.status = "INVALID"

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_published_version_requires_published_at(db_session):
    product, _ = create_test_product(db_session, "PUBLISHED-NO-DATE")

    version = create_test_version(db_session, product)

    version.status = "PUBLISHED"
    version.published_at = None

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_draft_version_cannot_have_published_at(db_session):
    product, _ = create_test_product(db_session, "DRAFT-WITH-DATE")

    version = create_test_version(db_session, product)

    version.status = "DRAFT"
    version.published_at = datetime(
        2026, 1, 1, 12, 0, tzinfo=timezone.utc
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_current_version_must_belong_to_same_product(db_session):
    product_a, _ = create_test_product(db_session, "VERSION-OWNER-A")
    product_b, _ = create_test_product(db_session, "VERSION-OWNER-B")

    version_b = create_test_version(db_session, product_b)

    # Attempt to assign Product B's version to Product A.
    product_a.current_version_id = version_b.id

    with pytest.raises(IntegrityError):
        db_session.flush()

@pytest.mark.integration
def test_product_media_rejects_invalid_media_type(db_session):
    product, _ = create_test_product(db_session, "INVALID-MEDIA-TYPE")

    media = ProductMedia(
        product_id=product.id,
        media_type="AUDIO",
        storage_key="test/invalid-type.mp3",
        original_filename="invalid.mp3",
        mime_type="audio/mpeg",
        file_size_bytes=100,
    )

    db_session.add(media)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_media_file_size_cannot_be_negative(db_session):
    product, _ = create_test_product(db_session, "NEGATIVE-MEDIA-SIZE")

    media = ProductMedia(
        product_id=product.id,
        media_type="IMAGE",
        storage_key="test/negative-size.jpg",
        original_filename="negative.jpg",
        mime_type="image/jpeg",
        file_size_bytes=-1,
    )

    db_session.add(media)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_media_storage_key_must_be_unique(db_session):
    product, _ = create_test_product(db_session, "DUPLICATE-STORAGE")

    first_media = ProductMedia(
        product_id=product.id,
        media_type="IMAGE",
        storage_key="test/shared-image.jpg",
        original_filename="first.jpg",
        mime_type="image/jpeg",
        file_size_bytes=100,
    )

    db_session.add(first_media)
    db_session.flush()

    duplicate_media = ProductMedia(
        product_id=product.id,
        media_type="IMAGE",
        storage_key="test/shared-image.jpg",
        original_filename="second.jpg",
        mime_type="image/jpeg",
        file_size_bytes=200,
    )

    db_session.add(duplicate_media)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_product_media_version_must_belong_to_same_product(db_session):
    product_a, _ = create_test_product(db_session, "MEDIA-OWNER-A")
    product_b, _ = create_test_product(db_session, "MEDIA-OWNER-B")

    version_b = create_test_version(db_session, product_b)

    media = ProductMedia(
        product_id=product_a.id,
        version_id=version_b.id,
        media_type="IMAGE",
        storage_key="test/wrong-product-version.jpg",
        original_filename="image.jpg",
        mime_type="image/jpeg",
        file_size_bytes=100,
    )

    db_session.add(media)

    with pytest.raises(IntegrityError):
        db_session.flush()