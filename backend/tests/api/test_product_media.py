import io

import pytest

from pathlib import Path
from uuid import uuid4

from PIL import Image
from sqlalchemy.exc import IntegrityError

from app.api.v1 import product_media as media_api
from app.services import media_service, media_storage


def create_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(
        buffer,
        format="PNG",
    )
    return buffer.getvalue()


@pytest.fixture
def isolated_media_storage(tmp_path, monkeypatch):
    async def store_in_temporary_directory(upload, media_type):
        return await media_storage.store_upload(
            upload,
            media_type,
            tmp_path,
        )

    monkeypatch.setattr(
        media_api,
        "store_upload",
        store_in_temporary_directory,
    )

    monkeypatch.setattr(
        media_service,
        "DEFAULT_STORAGE_ROOT",
        tmp_path,
    )

    return tmp_path


def create_product(client, sku="MEDIA-001"):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": "Media Test Product",
        },
    )

    assert response.status_code == 201
    return response.json()


def upload_image(
    client,
    product_id,
    *,
    version_id=None,
    filename="test.png",
    content=None,
):
    data = {
        "media_type": "IMAGE",
        "display_order": "0",
        "alt_text": "Test image",
    }

    if version_id is not None:
        data["version_id"] = str(version_id)

    return client.post(
        f"/api/v1/products/{product_id}/media",
        data=data,
        files={
            "file": (
                filename,
                content if content is not None else create_png(),
                "image/png",
            )
        },
    )


def assert_storage_empty(storage_root: Path):
    for directory in ("products", "documents", "temporary"):
        path = storage_root / directory

        if path.exists():
            assert list(path.iterdir()) == []


@pytest.mark.api
def test_upload_list_download_and_delete_media(
    client,
    isolated_media_storage,
):
    product = create_product(client)

    response = upload_image(client, product["id"])

    assert response.status_code == 201

    media = response.json()

    assert media["product_id"] == product["id"]
    assert media["media_type"] == "IMAGE"
    assert media["mime_type"] == "image/png"
    assert media["original_filename"] == "test.png"
    assert media["file_size_bytes"] > 0
    assert media["checksum_sha256"] is not None

    stored_files = list(
        (isolated_media_storage / "products").iterdir()
    )
    assert len(stored_files) == 1

    stored_file = stored_files[0]
    assert stored_file.is_file()

    listing = client.get(
        f"/api/v1/products/{product['id']}/media"
    )

    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == media["id"]

    details = client.get(
        f"/api/v1/products/{product['id']}/media/{media['id']}"
    )

    assert details.status_code == 200
    assert details.json()["id"] == media["id"]

    download = client.get(
        f"/api/v1/products/{product['id']}/media/{media['id']}/file"
    )

    assert download.status_code == 200
    assert download.content == create_png()
    assert download.headers["x-content-type-options"] == "nosniff"

    deletion = client.delete(
        f"/api/v1/products/{product['id']}/media/{media['id']}"
    )

    assert deletion.status_code == 200
    assert deletion.json()["id"] == media["id"]
    assert not stored_file.exists()

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "PRODUCT_MEDIA", "entity_id": media["id"]},
    )
    assert audits.status_code == 200
    assert {item["action"] for item in audits.json()["items"]} == {
        "PRODUCT_MEDIA_UPLOADED", "PRODUCT_MEDIA_DELETED",
    }

    listing_after_delete = client.get(
        f"/api/v1/products/{product['id']}/media"
    )

    assert listing_after_delete.status_code == 200
    assert listing_after_delete.json() == []


@pytest.mark.api
def test_upload_for_nonexistent_product_cleans_up_file(
    client,
    isolated_media_storage,
):
    response = upload_image(
        client,
        str(uuid4()),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found."

    assert_storage_empty(isolated_media_storage)


@pytest.mark.api
def test_upload_for_archived_product_cleans_up_file(
    client,
    isolated_media_storage,
):
    product = create_product(client, "MEDIA-002")

    archive = client.delete(
        f"/api/v1/products/{product['id']}"
    )

    assert archive.status_code == 200

    response = upload_image(
        client,
        product["id"],
    )

    assert response.status_code == 409
    assert_storage_empty(isolated_media_storage)


@pytest.mark.api
def test_invalid_image_upload_is_rejected(
    client,
    isolated_media_storage,
):
    product = create_product(client, "MEDIA-003")

    response = upload_image(
        client,
        product["id"],
        content=b"This is not an image.",
    )

    assert response.status_code == 400
    assert_storage_empty(isolated_media_storage)


@pytest.mark.api
def test_upload_media_to_draft_version(
    client,
    isolated_media_storage,
):
    product = create_product(client, "MEDIA-004")

    version_response = client.post(
        f"/api/v1/products/{product['id']}/versions",
        json={
            "content_snapshot": {
                "title": "Draft product content",
            }
        },
    )

    assert version_response.status_code == 201

    version = version_response.json()

    response = upload_image(
        client,
        product["id"],
        version_id=version["id"],
    )

    assert response.status_code == 201
    assert response.json()["version_id"] == version["id"]


@pytest.mark.api
def test_upload_to_published_version_is_rejected_and_cleaned(
    client,
    isolated_media_storage,
):
    product = create_product(client, "MEDIA-005")

    version_response = client.post(
        f"/api/v1/products/{product['id']}/versions",
        json={
            "content_snapshot": {
                "title": "Published product content",
            }
        },
    )

    assert version_response.status_code == 201

    version = version_response.json()

    publish_response = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{version['id']}/publish"
    )

    assert publish_response.status_code == 200

    response = upload_image(
        client,
        product["id"],
        version_id=version["id"],
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Media can only be attached to draft versions."
    )

    assert_storage_empty(isolated_media_storage)


@pytest.mark.api
def test_upload_with_version_from_another_product_is_rejected(
    client,
    isolated_media_storage,
):
    first_product = create_product(client, "MEDIA-006")
    second_product = create_product(client, "MEDIA-007")

    version_response = client.post(
        f"/api/v1/products/{first_product['id']}/versions",
        json={
            "content_snapshot": {
                "title": "Other product version",
            }
        },
    )

    assert version_response.status_code == 201

    version = version_response.json()

    response = upload_image(
        client,
        second_product["id"],
        version_id=version["id"],
    )

    assert response.status_code == 404
    assert_storage_empty(isolated_media_storage)


@pytest.mark.api
def test_database_failure_cleans_up_uploaded_file(
    client,
    isolated_media_storage,
    monkeypatch,
):
    product = create_product(client, "MEDIA-008")

    def fail_registration(*args, **kwargs):
        raise IntegrityError(
            "simulated insert",
            {},
            Exception("simulated database failure"),
        )

    monkeypatch.setattr(
        media_api,
        "create_product_media",
        fail_registration,
    )

    response = upload_image(
        client,
        product["id"],
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Media metadata could not be saved."
    )

    assert_storage_empty(isolated_media_storage)


@pytest.mark.api
def test_list_media_for_nonexistent_product_returns_404(client):
    response = client.get(
        f"/api/v1/products/{uuid4()}/media"
    )

    assert response.status_code == 404


@pytest.mark.api
def test_get_nonexistent_media_returns_404(client):
    product = create_product(client, "MEDIA-009")

    response = client.get(
        f"/api/v1/products/{product['id']}/media/{uuid4()}"
    )

    assert response.status_code == 404


@pytest.mark.api
def test_delete_nonexistent_media_returns_404(client):
    product = create_product(client, "MEDIA-010")

    response = client.delete(
        f"/api/v1/products/{product['id']}/media/{uuid4()}"
    )

    assert response.status_code == 404


@pytest.fixture
def client(admin_client):
    """Administrative API tests run as an authenticated super-admin."""
    return admin_client
