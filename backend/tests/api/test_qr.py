import csv
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from uuid import uuid4

import pytest
from PIL import Image

from app.models import QRAllocation, QRCode, Region


def create_product(client, sku=None, name="QR API Test Product"):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": sku or f"QR-API-{uuid4().hex[:12]}",
            "name": name,
        },
    )

    assert response.status_code == 201
    return response.json()


def create_region(db_session, active=True, name=None):
    suffix = uuid4().hex[:12]

    region = Region(
        name=name or f"QR API Region {suffix}",
        region_code=f"QR-API-{suffix}",
        region_type="TEST",
        is_active=active,
    )

    db_session.add(region)
    db_session.flush()

    return region


@pytest.mark.api
def test_create_list_and_get_qr_batch(client):
    creation = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 5},
    )

    assert creation.status_code == 201

    batch = creation.json()

    assert batch["quantity"] == 5
    assert batch["generation_status"] == "GENERATED"
    assert batch["batch_code"].startswith("QRB-")

    batch_id = batch["id"]

    listing = client.get("/api/v1/qr/batches")

    assert listing.status_code == 200
    assert any(item["id"] == batch_id for item in listing.json())

    details = client.get(f"/api/v1/qr/batches/{batch_id}")

    assert details.status_code == 200
    assert details.json()["id"] == batch_id

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "QR_BATCH", "entity_id": batch_id},
    )
    assert audits.status_code == 200
    assert any(item["action"] == "QR_BATCH_CREATED" for item in audits.json()["items"])
    assert all(item["admin_id"] for item in audits.json()["items"])

    codes = client.get(
        f"/api/v1/qr/batches/{batch_id}/codes"
    )

    assert codes.status_code == 200
    assert len(codes.json()) == 5

    tokens = [code["token"] for code in codes.json()]
    assert len(set(tokens)) == 5

    for code in codes.json():
        assert code["scan_url"].endswith(f"/q/{code['token']}")


@pytest.mark.api
def test_get_qr_code_by_id(client):
    batch = client.post("/api/v1/qr/batches", json={"quantity": 1})
    assert batch.status_code == 201
    code = client.get(
        f"/api/v1/qr/batches/{batch.json()['id']}/codes"
    ).json()[0]

    response = client.get(f"/api/v1/qr/codes/{code['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert {key: value for key, value in detail.items() if key != "created_at"} == {
        key: value for key, value in code.items() if key != "created_at"
    }
    assert datetime.fromisoformat(detail["created_at"].replace("Z", "+00:00")) == datetime.fromisoformat(
        code["created_at"].replace("Z", "+00:00")
    )

    missing = client.get(f"/api/v1/qr/codes/{uuid4()}")
    assert missing.status_code == 404


@pytest.mark.api
def test_create_batch_with_product_and_region(client, db_session):
    product = create_product(client)
    region = create_region(db_session)

    response = client.post(
        "/api/v1/qr/batches",
        json={
            "quantity": 3,
            "requested_product_id": product["id"],
            "requested_region_id": str(region.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["requested_product_id"] == product["id"]
    assert response.json()["requested_region_id"] == str(region.id)
    assert response.json()["current_product_id"] == product["id"]
    assert response.json()["current_region_id"] == str(region.id)
    assert response.json()["allocation_status"] == "ALLOCATED"
    qr_codes = client.get(
        f"/api/v1/qr/batches/{response.json()['id']}/codes"
    ).json()
    code_ids = {code["id"] for code in qr_codes}
    allocations = db_session.query(QRAllocation).filter(
        QRAllocation.qr_code_id.in_(code_ids),
        QRAllocation.ended_at.is_(None),
    ).all()
    assert len(allocations) == 3
    assert {str(allocation.product_id) for allocation in allocations} == {product["id"]}
    assert {allocation.region_id for allocation in allocations} == {region.id}


@pytest.mark.api
def test_batch_reassignment_is_reflected_as_current_allocation(client, db_session):
    first_product = create_product(client)
    first_region = create_region(db_session)
    next_product = create_product(client, name='=HYPERLINK("https://example.com")')
    next_region = create_region(db_session, name="+SUM(1,1)")
    batch = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 2},
    ).json()

    first_assignment = client.put(
        f"/api/v1/qr/batches/{batch['id']}/allocation",
        json={
            "product_id": first_product["id"],
            "region_id": str(first_region.id),
        },
    )
    assert first_assignment.status_code == 200

    reassignment = client.put(
        f"/api/v1/qr/batches/{batch['id']}/allocation",
        json={
            "product_id": next_product["id"],
            "region_id": str(next_region.id),
        },
    )
    assert reassignment.status_code == 200
    assert reassignment.json()["reassigned_count"] == 2

    export = client.get(f"/api/v1/qr/batches/{batch['id']}/share?format=png-zip")
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        csv_name = next(name for name in archive.namelist() if name.endswith("scan-links.csv"))
        exported_codes = list(csv.DictReader(io.StringIO(
            archive.read(csv_name).decode("utf-8-sig")
        )))
    assert len(exported_codes) == 2
    assert all(code["product_name"] == "'=HYPERLINK(\"https://example.com\")" for code in exported_codes)
    assert all(code["region_name"] == "'+SUM(1,1)" for code in exported_codes)
    assert all(code["product_sku"] == next_product["sku"] for code in exported_codes)
    assert all(code["region_code"] == next_region.region_code for code in exported_codes)

    listed = client.get("/api/v1/qr/batches").json()
    current = next(item for item in listed if item["id"] == batch["id"])
    details = client.get(f"/api/v1/qr/batches/{batch['id']}").json()
    for current_batch in (current, details):
        assert current_batch["current_product_id"] == next_product["id"]
        assert current_batch["current_region_id"] == str(next_region.id)
        assert current_batch["allocation_status"] == "ALLOCATED"
        assert current_batch["active_code_count"] == 2
        assert current_batch["allocated_code_count"] == 2

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "QR_BATCH", "entity_id": batch["id"]},
    )
    assert audits.status_code == 200
    assert sum(item["action"] == "QR_BATCH_ALLOCATED" for item in audits.json()["items"]) == 2
    assert all(item["admin_id"] for item in audits.json()["items"])


@pytest.mark.api
def test_batch_share_download_contains_qr_svgs_and_scan_link_csv(client):
    batch = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 2},
    ).json()

    response = client.get(f"/api/v1/qr/batches/{batch['id']}/share")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        qr_files = [name for name in names if name.endswith(".svg")]
        csv_name = next(name for name in names if name.endswith("scan-links.csv"))
        readme_name = next(name for name in names if name.endswith("README.txt"))
        assert len(qr_files) == 2
        assert archive.read(qr_files[0]).lstrip().startswith(b"<?xml")
        assert b"location policy" in archive.read(readme_name)

        links = list(csv.DictReader(io.StringIO(
            archive.read(csv_name).decode("utf-8-sig")
        )))
        assert len(links) == 2
        assert all(link["status"] == "ACTIVE" for link in links)
        assert all(link["scan_url"].endswith(link["token"]) for link in links)


@pytest.mark.api
def test_batch_share_download_contains_png_folder(client):
    batch = client.post("/api/v1/qr/batches", json={"quantity": 2}).json()

    response = client.get(f"/api/v1/qr/batches/{batch['id']}/share?format=png-zip")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        png_files = [name for name in names if name.endswith(".png")]
        assert len(png_files) == 2
        assert all("/png/" in name for name in png_files)
        assert all(archive.read(name).startswith(b"\x89PNG\r\n\x1a\n") for name in png_files)
        csv_name = next(name for name in names if name.endswith("scan-links.csv"))
        readme_name = next(name for name in names if name.endswith("README.txt"))
        links = list(csv.DictReader(io.StringIO(
            archive.read(csv_name).decode("utf-8-sig")
        )))
        assert len(links) == 2
        assert all(link["status"] == "ACTIVE" for link in links)
        assert all(link["scan_url"].endswith(link["token"]) for link in links)
        assert b"location policy" in archive.read(readme_name)
        assert all(name.endswith((".png", "scan-links.csv", "README.txt")) for name in names)


@pytest.mark.api
def test_batch_share_download_contains_printable_pdf(client):
    batch = client.post("/api/v1/qr/batches", json={"quantity": 2}).json()

    response = client.get(f"/api/v1/qr/batches/{batch['id']}/share?format=pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")


@pytest.mark.api
def test_batch_allocation_requires_product_and_region_together(client):
    product = create_product(client)
    response = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 1, "requested_product_id": product["id"]},
    )
    assert response.status_code == 422


@pytest.mark.api
def test_retire_batch_revokes_codes_and_closes_allocations(client, db_session):
    product = create_product(client)
    region = create_region(db_session)
    batch = client.post(
        "/api/v1/qr/batches",
        json={
            "quantity": 2,
            "requested_product_id": product["id"],
            "requested_region_id": str(region.id),
        },
    ).json()

    retired = client.post(f"/api/v1/qr/batches/{batch['id']}/retire")
    assert retired.status_code == 200
    assert retired.json()["revoked_count"] == 2
    assert retired.json()["retired_at"] is not None
    assert client.get(f"/api/v1/qr/batches/{batch['id']}").json()["retired_at"] == retired.json()["retired_at"]

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "QR_BATCH", "entity_id": batch["id"]},
    )
    assert audits.status_code == 200
    assert {item["action"] for item in audits.json()["items"]} == {
        "QR_BATCH_CREATED", "QR_BATCH_RETIRED",
    }

    codes = client.get(f"/api/v1/qr/batches/{batch['id']}/codes").json()
    assert {code["status"] for code in codes} == {"REVOKED"}
    for code in codes:
        active = client.get(f"/api/v1/qr/codes/{code['id']}/allocation")
        history = client.get(
            f"/api/v1/qr/codes/{code['id']}/allocation/history"
        )
        assert active.status_code == 200
        assert active.json() is None
        assert history.json()[0]["ended_at"] is not None

    repeated = client.post(f"/api/v1/qr/batches/{batch['id']}/retire")
    assert repeated.json()["revoked_count"] == 0
    assert repeated.json()["retired_at"] == retired.json()["retired_at"]


@pytest.mark.api
def test_duplicate_batch_code_returns_conflict(client):
    payload = {
        "quantity": 1,
        "batch_code": "QR-API-DUPLICATE",
    }

    first = client.post("/api/v1/qr/batches", json=payload)
    second = client.post("/api/v1/qr/batches", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.api
def test_invalid_batch_quantity_is_rejected(client):
    for quantity in (0, 5001):
        response = client.post(
            "/api/v1/qr/batches",
            json={"quantity": quantity},
        )

        assert response.status_code == 422


@pytest.mark.api
def test_nonexistent_product_returns_404(client):
    response = client.post(
        "/api/v1/qr/batches",
        json={
            "quantity": 1,
            "requested_product_id": str(uuid4()),
            "requested_region_id": str(uuid4()),
        },
    )

    assert response.status_code == 404


@pytest.mark.api
def test_inactive_region_returns_conflict(client, db_session):
    product = create_product(client)
    region = create_region(db_session, active=False)

    response = client.post(
        "/api/v1/qr/batches",
        json={
            "quantity": 1,
            "requested_product_id": product["id"],
            "requested_region_id": str(region.id),
        },
    )

    assert response.status_code == 409


@pytest.mark.api
def test_nonexistent_batch_returns_404(client):
    response = client.get(
        f"/api/v1/qr/batches/{uuid4()}"
    )

    assert response.status_code == 404

    codes = client.get(
        f"/api/v1/qr/batches/{uuid4()}/codes"
    )

    assert codes.status_code == 404


@pytest.mark.api
def test_png_qr_image_is_valid(client):
    batch = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 1},
    ).json()

    code = client.get(
        f"/api/v1/qr/batches/{batch['id']}/codes"
    ).json()[0]

    response = client.get(
        f"/api/v1/qr/codes/{code['id']}/image"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["x-content-type-options"] == "nosniff"

    image = Image.open(io.BytesIO(response.content))
    image.verify()


@pytest.mark.api
def test_svg_qr_image_is_valid(client):
    batch = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 1},
    ).json()

    code = client.get(
        f"/api/v1/qr/batches/{batch['id']}/codes"
    ).json()[0]

    response = client.get(
        f"/api/v1/qr/codes/{code['id']}/image",
        params={"format": "svg"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")

    root = ET.fromstring(response.content)

    assert root.tag.endswith("svg")


@pytest.mark.api
def test_invalid_qr_image_format_is_rejected(client):
    batch = client.post(
        "/api/v1/qr/batches",
        json={"quantity": 1},
    ).json()

    code = client.get(
        f"/api/v1/qr/batches/{batch['id']}/codes"
    ).json()[0]

    response = client.get(
        f"/api/v1/qr/codes/{code['id']}/image",
        params={"format": "jpg"},
    )

    assert response.status_code == 422


@pytest.mark.api
def test_nonexistent_qr_image_returns_404(client):
    response = client.get(
        f"/api/v1/qr/codes/{uuid4()}/image"
    )

    assert response.status_code == 404


@pytest.fixture
def client(admin_client):
    """Administrative API tests run as an authenticated super-admin."""
    return admin_client
