from uuid import uuid4

import pytest

from app.models import Product, QRCode, Region, QRAllocation


def create_product(client, db_session, status="DRAFT"):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": f"ALLOC-{uuid4().hex[:12]}",
            "name": "Allocation Test Product",
        },
    )

    assert response.status_code == 201

    product_id = response.json()["id"]

    product = db_session.get(Product, product_id)
    product.status = status
    db_session.flush()

    return product


def create_region(db_session, active=True):
    suffix = uuid4().hex[:12]

    region = Region(
        name=f"Allocation Region {suffix}",
        region_code=f"ALLOC-{suffix}",
        region_type="TEST",
        is_active=active,
    )

    db_session.add(region)
    db_session.flush()

    return region


def create_qr_codes(client, quantity=2):
    batch_response = client.post(
        "/api/v1/qr/batches",
        json={"quantity": quantity},
    )

    assert batch_response.status_code == 201

    batch_id = batch_response.json()["id"]

    codes_response = client.get(
        f"/api/v1/qr/batches/{batch_id}/codes"
    )

    assert codes_response.status_code == 200

    return codes_response.json()


def allocate(client, qr_code_ids, product_id, region_id):
    return client.post(
        "/api/v1/qr/allocations",
        json={
            "qr_code_ids": qr_code_ids,
            "product_id": str(product_id),
            "region_id": str(region_id),
        },
    )


@pytest.mark.api
def test_bulk_allocate_qr_codes(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session)
    codes = create_qr_codes(client, quantity=3)

    response = allocate(
        client,
        [code["id"] for code in codes],
        product.id,
        region.id,
    )

    assert response.status_code == 201
    assert len(response.json()) == 3

    for allocation in response.json():
        assert allocation["product_id"] == str(product.id)
        assert allocation["region_id"] == str(region.id)
        assert allocation["ended_at"] is None


@pytest.mark.api
def test_get_active_allocation_and_history(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    allocation_response = allocate(
        client,
        [code["id"]],
        product.id,
        region.id,
    )

    assert allocation_response.status_code == 201

    active_response = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )

    assert active_response.status_code == 200
    assert active_response.json()["id"] == allocation_response.json()[0]["id"]

    history_response = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation/history"
    )

    assert history_response.status_code == 200
    assert len(history_response.json()) == 1


@pytest.mark.api
def test_qr_without_allocation_returns_null(client):
    code = create_qr_codes(client, quantity=1)[0]

    response = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.api
def test_already_allocated_qr_returns_conflict(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    first = allocate(
        client,
        [code["id"]],
        product.id,
        region.id,
    )

    second = allocate(
        client,
        [code["id"]],
        product.id,
        region.id,
    )

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.api
def test_bulk_allocation_is_atomic_when_one_qr_is_already_allocated(
    client,
    db_session,
):
    product = create_product(client, db_session)
    region = create_region(db_session)
    codes = create_qr_codes(client, quantity=2)

    first = allocate(
        client,
        [codes[0]["id"]],
        product.id,
        region.id,
    )

    assert first.status_code == 201

    second = allocate(
        client,
        [codes[0]["id"], codes[1]["id"]],
        product.id,
        region.id,
    )

    assert second.status_code == 409

    # The previously unallocated QR must remain unallocated.
    untouched = client.get(
        f"/api/v1/qr/codes/{codes[1]['id']}/allocation"
    )

    assert untouched.status_code == 200
    assert untouched.json() is None


@pytest.mark.api
def test_nonexistent_qr_code_returns_404_without_partial_allocation(
    client,
    db_session,
):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    response = allocate(
        client,
        [code["id"], str(uuid4())],
        product.id,
        region.id,
    )

    assert response.status_code == 404

    active = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )

    assert active.status_code == 200
    assert active.json() is None


@pytest.mark.api
def test_inactive_qr_code_cannot_be_allocated(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    qr_code = db_session.get(QRCode, code["id"])
    from datetime import datetime, timezone

    qr_code.status = "INACTIVE"
    qr_code.deactivated_at = datetime.now(timezone.utc)
    db_session.flush()

    response = allocate(
        client,
        [code["id"]],
        product.id,
        region.id,
    )

    assert response.status_code == 409


@pytest.mark.api
def test_archived_product_cannot_receive_allocations(client, db_session):
    product = create_product(client, db_session, status="ARCHIVED")
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    response = allocate(
        client,
        [code["id"]],
        product.id,
        region.id,
    )

    assert response.status_code == 409


@pytest.mark.api
def test_inactive_region_cannot_receive_allocations(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session, active=False)
    code = create_qr_codes(client, quantity=1)[0]

    response = allocate(
        client,
        [code["id"]],
        product.id,
        region.id,
    )

    assert response.status_code == 409


@pytest.mark.api
def test_duplicate_qr_ids_are_rejected(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    response = allocate(
        client,
        [code["id"], code["id"]],
        product.id,
        region.id,
    )

    assert response.status_code == 422


@pytest.mark.api
def test_nonexistent_product_returns_404(client):
    region_id = uuid4()
    code = create_qr_codes(client, quantity=1)[0]

    response = allocate(
        client,
        [code["id"]],
        uuid4(),
        region_id,
    )

    assert response.status_code == 404


@pytest.mark.api
def test_nonexistent_region_returns_404(client, db_session):
    product = create_product(client, db_session)
    code = create_qr_codes(client, quantity=1)[0]

    response = allocate(
        client,
        [code["id"]],
        product.id,
        uuid4(),
    )

    assert response.status_code == 404


@pytest.mark.api
def test_allocation_history_returns_404_for_unknown_qr(client):
    response = client.get(
        f"/api/v1/qr/codes/{uuid4()}/allocation/history"
    )

    assert response.status_code == 404


@pytest.mark.api
def test_successful_reassignment_preserves_allocation_history(
    client,
    db_session,
):
    original_product = create_product(client, db_session)
    original_region = create_region(db_session)
    new_product = create_product(client, db_session)
    new_region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    initial = allocate(
        client,
        [code["id"]],
        original_product.id,
        original_region.id,
    )
    assert initial.status_code == 201
    old_allocation_id = initial.json()[0]["id"]

    response = client.put(
        f"/api/v1/qr/codes/{code['id']}/allocation",
        json={
            "product_id": str(new_product.id),
            "region_id": str(new_region.id),
            "reason": "Product reassignment test",
        },
    )

    assert response.status_code == 200
    new_allocation = response.json()
    assert new_allocation["product_id"] == str(new_product.id)
    assert new_allocation["region_id"] == str(new_region.id)
    assert new_allocation["reason"] == "Product reassignment test"

    history = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation/history"
    )
    assert history.status_code == 200
    assert len(history.json()) == 2

    records = {item["id"]: item for item in history.json()}
    old_allocation = records[old_allocation_id]
    new_allocation_from_history = records[new_allocation["id"]]

    assert old_allocation["ended_at"] is not None
    assert old_allocation["ended_at"] == new_allocation_from_history["assigned_at"]
    assert new_allocation_from_history["ended_at"] is None

    active = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )
    assert active.status_code == 200
    assert active.json()["id"] == new_allocation["id"]

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "QR_CODE", "entity_id": code["id"]},
    )
    assert audits.status_code == 200
    assert any(
        item["action"] == "QR_CODE_REASSIGNED"
        for item in audits.json()["items"]
    ), audits.json()
    assert all(item["admin_id"] for item in audits.json()["items"])


@pytest.mark.api
def test_reassignment_to_same_product_and_region_returns_conflict(
    client,
    db_session,
):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    initial = allocate(client, [code["id"]], product.id, region.id)
    assert initial.status_code == 201

    response = client.put(
        f"/api/v1/qr/codes/{code['id']}/allocation",
        json={
            "product_id": str(product.id),
            "region_id": str(region.id),
        },
    )

    assert response.status_code == 409

    history = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation/history"
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["ended_at"] is None


@pytest.mark.api
def test_reassign_nonexistent_qr_returns_404(client, db_session):
    product = create_product(client, db_session)
    region = create_region(db_session)

    response = client.put(
        f"/api/v1/qr/codes/{uuid4()}/allocation",
        json={
            "product_id": str(product.id),
            "region_id": str(region.id),
        },
    )

    assert response.status_code == 404


@pytest.mark.api
def test_reassign_inactive_qr_returns_conflict(client, db_session):
    from datetime import datetime, timezone

    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    qr_code = db_session.get(QRCode, code["id"])
    qr_code.status = "INACTIVE"
    qr_code.deactivated_at = datetime.now(timezone.utc)
    db_session.flush()

    response = client.put(
        f"/api/v1/qr/codes/{code['id']}/allocation",
        json={
            "product_id": str(product.id),
            "region_id": str(region.id),
        },
    )

    assert response.status_code == 409


@pytest.mark.api
def test_reassign_qr_without_active_allocation_returns_conflict(
    client,
    db_session,
):
    product = create_product(client, db_session)
    region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    response = client.put(
        f"/api/v1/qr/codes/{code['id']}/allocation",
        json={
            "product_id": str(product.id),
            "region_id": str(region.id),
        },
    )

    assert response.status_code == 409


@pytest.mark.api
def test_reassignment_to_archived_product_preserves_old_allocation(
    client,
    db_session,
):
    original_product = create_product(client, db_session)
    original_region = create_region(db_session)
    archived_product = create_product(
        client,
        db_session,
        status="ARCHIVED",
    )
    new_region = create_region(db_session)
    code = create_qr_codes(client, quantity=1)[0]

    initial = allocate(
        client,
        [code["id"]],
        original_product.id,
        original_region.id,
    )
    assert initial.status_code == 201

    response = client.put(
        f"/api/v1/qr/codes/{code['id']}/allocation",
        json={
            "product_id": str(archived_product.id),
            "region_id": str(new_region.id),
        },
    )

    assert response.status_code == 409

    active = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )
    assert active.status_code == 200
    assert active.json()["product_id"] == str(original_product.id)
    assert active.json()["ended_at"] is None


@pytest.mark.api
def test_reassignment_to_inactive_region_preserves_old_allocation(
    client,
    db_session,
):
    original_product = create_product(client, db_session)
    original_region = create_region(db_session)
    new_product = create_product(client, db_session)
    inactive_region = create_region(db_session, active=False)
    code = create_qr_codes(client, quantity=1)[0]

    initial = allocate(
        client,
        [code["id"]],
        original_product.id,
        original_region.id,
    )
    assert initial.status_code == 201

    response = client.put(
        f"/api/v1/qr/codes/{code['id']}/allocation",
        json={
            "product_id": str(new_product.id),
            "region_id": str(inactive_region.id),
        },
    )

    assert response.status_code == 409

    active = client.get(
        f"/api/v1/qr/codes/{code['id']}/allocation"
    )
    assert active.status_code == 200
    assert active.json()["product_id"] == str(original_product.id)
    assert active.json()["region_id"] == str(original_region.id)
    assert active.json()["ended_at"] is None


@pytest.fixture
def client(admin_client):
    """Administrative API tests run as an authenticated super-admin."""
    return admin_client
