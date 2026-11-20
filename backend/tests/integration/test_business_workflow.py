import io
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from PIL import Image

from app.api.v1 import product_media as media_api
from app.services import media_service, media_storage


@pytest.fixture
def isolated_workflow_media_storage(tmp_path, monkeypatch):
    async def store_in_temporary_directory(upload, media_type):
        return await media_storage.store_upload(upload, media_type, tmp_path)

    monkeypatch.setattr(media_api, "store_upload", store_in_temporary_directory)
    monkeypatch.setattr(media_service, "DEFAULT_STORAGE_ROOT", tmp_path)
    return tmp_path


def _png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "#2463eb").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.api
def test_product_to_qr_scan_media_analytics_and_audit_workflow(
    admin_client,
    isolated_workflow_media_storage,
):
    suffix = uuid4().hex[:12]

    category_response = admin_client.post(
        "/api/v1/categories",
        json={"name": f"Workflow category {suffix}"},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    product_response = admin_client.post(
        "/api/v1/products",
        json={
            "sku": f"WORKFLOW-{suffix}",
            "name": "Workflow product",
            "category_id": category_id,
        },
    )
    assert product_response.status_code == 201
    product = product_response.json()

    region_response = admin_client.post(
        "/api/v1/regions",
        json={
            "name": f"Workflow region {suffix}",
            "region_code": f"WF-{suffix}",
            "region_type": "TEST",
        },
    )
    assert region_response.status_code == 201
    region_id = region_response.json()["id"]

    version_response = admin_client.post(
        f"/api/v1/products/{product['id']}/versions",
        json={
            "content_snapshot": {
                "title": "Workflow product",
                "description": "Published through the integrated workflow.",
                "models": [{"name": "WF-1", "net_weight": "2 kg"}],
            }
        },
    )
    assert version_response.status_code == 201
    version = version_response.json()

    media_response = admin_client.post(
        f"/api/v1/products/{product['id']}/media",
        data={
            "media_type": "IMAGE",
            "version_id": version["id"],
            "display_order": "0",
            "alt_text": "Workflow product image",
        },
        files={"file": ("workflow.png", _png_bytes(), "image/png")},
    )
    assert media_response.status_code == 201
    media = media_response.json()

    publish_response = admin_client.post(
        f"/api/v1/products/{product['id']}/versions/{version['id']}/publish"
    )
    assert publish_response.status_code == 200

    policy_response = admin_client.post(
        "/api/v1/location-policies",
        json={
            "name": f"Workflow GPS policy {suffix}",
            "requirement": "MANDATORY",
            "method": "GPS_REQUIRED",
        },
    )
    assert policy_response.status_code == 201
    assignment_response = admin_client.post(
        "/api/v1/location-policy-assignments",
        json={
            "policy_id": policy_response.json()["id"],
            "scope_type": "PRODUCT",
            "product_id": product["id"],
        },
    )
    assert assignment_response.status_code == 201

    batch_response = admin_client.post(
        "/api/v1/qr/batches",
        json={
            "quantity": 1,
            "requested_product_id": product["id"],
            "requested_region_id": region_id,
        },
    )
    assert batch_response.status_code == 201
    batch = batch_response.json()
    assert batch["allocation_status"] == "ALLOCATED"

    codes_response = admin_client.get(f"/api/v1/qr/batches/{batch['id']}/codes")
    assert codes_response.status_code == 200
    assert len(codes_response.json()) == 1
    code = codes_response.json()[0]
    code_allocation_response = admin_client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )
    assert code_allocation_response.status_code == 200
    assert code_allocation_response.json()["product_id"] == product["id"]
    assert code_allocation_response.json()["region_id"] == region_id

    start_response = admin_client.post(
        "/api/v1/public/scans/start",
        json={"token": code["token"]},
    )
    assert start_response.status_code == 201
    scan_id = start_response.json()["scan_id"]
    assert start_response.json()["location_requested"] is True
    assert start_response.json()["location_method"] == "GPS_REQUIRED"

    completion_response = admin_client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={
            "location_status": "GPS",
            "latitude": 19.076,
            "longitude": 72.8777,
            "accuracy_meters": 25,
        },
    )
    assert completion_response.status_code == 200
    completed = completion_response.json()
    assert completed["result_status"] == "ALLOWED"
    assert completed["product"]["id"] == product["id"]
    assert completed["product"]["version_id"] == version["id"]
    assert completed["product"]["content_snapshot"]["models"][0]["net_weight"] == "2 kg"

    public_media_response = admin_client.get(f"/api/v1/public/scans/{scan_id}/media")
    assert public_media_response.status_code == 200
    assert [item["id"] for item in public_media_response.json()] == [media["id"]]
    media_download = admin_client.get(
        f"/api/v1/public/scans/{scan_id}/media/{media['id']}/file"
    )
    assert media_download.status_code == 200
    assert media_download.content == _png_bytes()

    today = datetime.now(timezone.utc).date().isoformat()
    analytics_response = admin_client.get(
        "/api/v1/analytics/scans",
        params={
            "from_date": today,
            "to_date": today,
            "product_id": product["id"],
            "qr_code_id": code["id"],
            "region_id": region_id,
        },
    )
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert analytics["summary"]["total"] == 1
    assert analytics["summary"]["allowed"] == 1
    assert analytics["location_analytics"]["location_statuses"]["GPS"] == 1
    assert analytics["products"][0]["product_id"] == product["id"]
    assert analytics["regions"][0]["region_id"] == region_id
    assert analytics["qr_codes"][0]["qr_code_id"] == code["id"]

    audit_response = admin_client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "PRODUCT_VERSION", "entity_id": version["id"]},
    )
    assert audit_response.status_code == 200
    assert {entry["action"] for entry in audit_response.json()["items"]} == {
        "PRODUCT_VERSION_CREATED",
        "PRODUCT_VERSION_PUBLISHED",
    }
    assert all(entry["admin_id"] for entry in audit_response.json()["items"])
