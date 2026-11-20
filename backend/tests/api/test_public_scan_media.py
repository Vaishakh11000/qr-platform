from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.models import (
    Product,
    ProductMedia,
    ProductVersion,
    QRAllocation,
    QRBatch,
    QRCode,
    Region,
    ScanEvent,
)
from app.services import media_service


def create_scan_fixture(db_session):
    suffix = uuid4().hex[:12]

    product = Product(
        sku=f"PUBLIC-MEDIA-{suffix}",
        name="Public Media Test Product",
        status="ACTIVE",
    )
    db_session.add(product)
    db_session.flush()

    version = ProductVersion(
        product_id=product.id,
        version_number=1,
        content_snapshot={"title": "Public Media Test"},
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(version)
    db_session.flush()

    product.current_version_id = version.id

    region = Region(
        name=f"Public Media Region {suffix}",
        region_code=f"PM-{suffix}",
        region_type="TEST",
        is_active=True,
    )
    db_session.add(region)
    db_session.flush()

    batch = QRBatch(
        batch_code=f"PUBLIC-MEDIA-{suffix}",
        quantity=1,
        generation_status="GENERATED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()

    qr = QRCode(
        batch_id=batch.id,
        token=f"public-media-{uuid4().hex}",
        status="ACTIVE",
    )
    db_session.add(qr)
    db_session.flush()

    allocation = QRAllocation(
        qr_code_id=qr.id,
        product_id=product.id,
        region_id=region.id,
    )
    db_session.add(allocation)
    db_session.commit()

    return product, version, qr


def create_media(db_session, product, version, storage_root, filename):
    storage_key = f"products/{filename}"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"public-media-test-content")

    media = ProductMedia(
        product_id=product.id,
        version_id=version.id,
        media_type="IMAGE",
        storage_key=storage_key,
        original_filename=filename,
        mime_type="image/png",
        file_size_bytes=file_path.stat().st_size,
        checksum_sha256=None,
        display_order=0,
        alt_text="Public test image",
    )
    db_session.add(media)
    db_session.commit()
    db_session.refresh(media)

    return media


def start_and_complete_scan(client, qr):
    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={"location_status": "SKIPPED"},
    )
    assert completion.status_code == 200
    assert completion.json()["result_status"] == "ALLOWED"

    return scan_id


@pytest.fixture
def isolated_public_media_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(
        media_service,
        "DEFAULT_STORAGE_ROOT",
        tmp_path,
    )
    return tmp_path


@pytest.mark.api
def test_public_scan_lists_and_downloads_only_its_version_media(
    client,
    db_session,
    isolated_public_media_storage,
):
    product, version, qr = create_scan_fixture(db_session)
    media = create_media(
        db_session,
        product,
        version,
        isolated_public_media_storage,
        "version-one.png",
    )

    scan_id = start_and_complete_scan(client, qr)

    listing = client.get(
        f"/api/v1/public/scans/{scan_id}/media"
    )

    assert listing.status_code == 200
    data = listing.json()
    assert len(data) == 1
    assert data[0]["id"] == str(media.id)
    assert data[0]["version_id"] == str(version.id)
    assert "storage_key" not in data[0]

    download = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media.id}/file"
    )

    assert download.status_code == 200
    assert download.content == b"public-media-test-content"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "no-store"


@pytest.mark.api
def test_pending_scan_cannot_access_media(
    client,
    db_session,
    isolated_public_media_storage,
):
    product, version, qr = create_scan_fixture(db_session)
    media = create_media(
        db_session,
        product,
        version,
        isolated_public_media_storage,
        "pending.png",
    )

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201
    scan_id = start.json()["scan_id"]

    listing = client.get(
        f"/api/v1/public/scans/{scan_id}/media"
    )
    download = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media.id}/file"
    )

    assert listing.status_code == 404
    assert download.status_code == 404


@pytest.mark.api
def test_blocked_scan_cannot_access_media(
    client,
    db_session,
    isolated_public_media_storage,
):
    product, version, qr = create_scan_fixture(db_session)
    media = create_media(
        db_session,
        product,
        version,
        isolated_public_media_storage,
        "blocked.png",
    )

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201
    scan_id = start.json()["scan_id"]

    event = db_session.get(ScanEvent, scan_id)
    event.result_status = "BLOCKED"
    event.completed_at = datetime.now(timezone.utc)
    db_session.commit()

    listing = client.get(
        f"/api/v1/public/scans/{scan_id}/media"
    )
    download = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media.id}/file"
    )

    assert listing.status_code == 404
    assert download.status_code == 404


@pytest.mark.api
def test_public_scan_cannot_download_media_from_another_version(
    client,
    db_session,
    isolated_public_media_storage,
):
    product, version, qr = create_scan_fixture(db_session)

    other_version = ProductVersion(
        product_id=product.id,
        version_number=2,
        content_snapshot={"title": "Different version"},
        status="DRAFT",
    )
    db_session.add(other_version)
    db_session.commit()
    db_session.refresh(other_version)

    other_media = create_media(
        db_session,
        product,
        other_version,
        isolated_public_media_storage,
        "other-version.png",
    )

    scan_id = start_and_complete_scan(client, qr)

    listing = client.get(
        f"/api/v1/public/scans/{scan_id}/media"
    )
    download = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{other_media.id}/file"
    )

    assert listing.status_code == 200
    assert listing.json() == []
    assert download.status_code == 404


@pytest.mark.api
def test_retired_version_remains_available_to_existing_scan(
    client,
    db_session,
    isolated_public_media_storage,
):
    product, version, qr = create_scan_fixture(db_session)
    media = create_media(
        db_session,
        product,
        version,
        isolated_public_media_storage,
        "retired-version.png",
    )

    scan_id = start_and_complete_scan(client, qr)

    version.status = "RETIRED"
    db_session.commit()

    listing = client.get(
        f"/api/v1/public/scans/{scan_id}/media"
    )
    download = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media.id}/file"
    )

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [str(media.id)]
    assert download.status_code == 200
    assert download.content == b"public-media-test-content"


@pytest.mark.api
def test_public_scan_returns_404_for_missing_scan_or_media(
    client,
):
    scan_id = uuid4()
    media_id = uuid4()

    listing = client.get(
        f"/api/v1/public/scans/{scan_id}/media"
    )
    download = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media_id}/file"
    )

    assert listing.status_code == 404
    assert download.status_code == 404


@pytest.mark.api
def test_public_scan_returns_404_when_media_file_is_missing(
    client,
    db_session,
    isolated_public_media_storage,
):
    product, version, qr = create_scan_fixture(db_session)
    media = create_media(
        db_session,
        product,
        version,
        isolated_public_media_storage,
        "missing-file.png",
    )

    scan_id = start_and_complete_scan(client, qr)

    (isolated_public_media_storage / media.storage_key).unlink()

    response = client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media.id}/file"
    )

    assert response.status_code == 404
