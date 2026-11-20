import pytest

from uuid import uuid4


@pytest.mark.api
def test_create_product(client):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": "PROD-001",
            "name": "Wireless Headphones",
            "short_description": "Bluetooth headphones",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sku"] == "PROD-001"
    assert data["name"] == "Wireless Headphones"
    assert data["short_description"] == "Bluetooth headphones"
    assert data["category_id"] is None
    assert data["status"] == "DRAFT"
    assert data["id"] is not None


@pytest.mark.api
def test_create_product_with_category(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    response = client.post(
        "/api/v1/products",
        json={
            "sku": "PROD-002",
            "name": "Smartphone",
            "category_id": category["id"],
        },
    )

    assert response.status_code == 201
    assert response.json()["category_id"] == category["id"]


@pytest.mark.api
def test_create_product_with_invalid_category(client):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": "PROD-003",
            "name": "Smartphone",
            "category_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product category not found."


@pytest.mark.api
def test_create_product_with_inactive_category(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Inactive Category"},
    ).json()

    client.delete(f"/api/v1/categories/{category['id']}")

    response = client.post(
        "/api/v1/products",
        json={
            "sku": "PROD-004",
            "name": "Smartphone",
            "category_id": category["id"],
        },
    )

    assert response.status_code == 409


@pytest.mark.api
def test_create_product_rejects_empty_name(client):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": "PROD-005",
            "name": "   ",
        },
    )

    assert response.status_code == 422


@pytest.mark.api
def test_create_product_rejects_missing_required_fields(client):
    response = client.post(
        "/api/v1/products",
        json={
            "short_description": "Product without required fields",
        },
    )

    assert response.status_code == 422


@pytest.mark.api
def test_create_product_rejects_duplicate_sku(client):
    payload = {
        "sku": "DUPLICATE-001",
        "name": "First Product",
    }

    first_response = client.post(
        "/api/v1/products",
        json=payload,
    )

    second_response = client.post(
        "/api/v1/products",
        json={
            "sku": "DUPLICATE-001",
            "name": "Second Product",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.api
def test_list_products(client):
    client.post(
        "/api/v1/products",
        json={"sku": "LIST-001", "name": "Product One"},
    )

    client.post(
        "/api/v1/products",
        json={"sku": "LIST-002", "name": "Product Two"},
    )

    response = client.get("/api/v1/products")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["sku"] for item in data} == {
        "LIST-001",
        "LIST-002",
    }


@pytest.mark.api
def test_list_products_with_pagination(client):
    for sku in ["PAGE-001", "PAGE-002", "PAGE-003"]:
        client.post(
            "/api/v1/products",
            json={"sku": sku, "name": sku},
        )

    response = client.get(
        "/api/v1/products",
        params={"offset": 1, "limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.api
def test_list_products_by_category(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    client.post(
        "/api/v1/products",
        json={
            "sku": "CAT-001",
            "name": "Phone",
            "category_id": category["id"],
        },
    )

    client.post(
        "/api/v1/products",
        json={
            "sku": "CAT-002",
            "name": "Laptop",
        },
    )

    response = client.get(
        "/api/v1/products",
        params={"category_id": category["id"]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["sku"] == "CAT-001"


@pytest.mark.api
def test_list_products_by_status(client):
    product = client.post(
        "/api/v1/products",
        json={"sku": "STATUS-001", "name": "Archived Product"},
    ).json()

    client.delete(f"/api/v1/products/{product['id']}")

    response = client.get(
        "/api/v1/products",
        params={"status": "ARCHIVED"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "ARCHIVED"


@pytest.mark.api
def test_list_products_rejects_invalid_status(client):
    response = client.get(
        "/api/v1/products",
        params={"status": "INVALID"},
    )

    assert response.status_code == 422


@pytest.mark.api
def test_get_product_by_id(client):
    product = client.post(
        "/api/v1/products",
        json={"sku": "GET-001", "name": "Test Product"},
    ).json()

    response = client.get(
        f"/api/v1/products/{product['id']}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == product["id"]
    assert response.json()["sku"] == "GET-001"


@pytest.mark.api
def test_get_nonexistent_product(client):
    response = client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000001",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found."


@pytest.mark.api
def test_update_product(client):
    product = client.post(
        "/api/v1/products",
        json={"sku": "UPDATE-001", "name": "Old Name"},
    ).json()

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={
            "name": "New Name",
            "short_description": "Updated description",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["short_description"] == "Updated description"


@pytest.mark.api
def test_update_product_category(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    product = client.post(
        "/api/v1/products",
        json={"sku": "UPDATE-002", "name": "Phone"},
    ).json()

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"category_id": category["id"]},
    )

    assert response.status_code == 200
    assert response.json()["category_id"] == category["id"]


@pytest.mark.api
def test_update_product_keeps_existing_inactive_category_but_cannot_assign_it(client):
    assigned_category = client.post(
        "/api/v1/categories",
        json={"name": "Assigned category"},
    ).json()
    other_category = client.post(
        "/api/v1/categories",
        json={"name": "Other category"},
    ).json()
    product = client.post(
        "/api/v1/products",
        json={
            "sku": "UPDATE-INACTIVE-CATEGORY",
            "name": "Phone",
            "category_id": assigned_category["id"],
        },
    ).json()

    client.delete(f"/api/v1/categories/{assigned_category['id']}")
    client.delete(f"/api/v1/categories/{other_category['id']}")

    update_existing = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Updated phone", "category_id": assigned_category["id"]},
    )
    assert update_existing.status_code == 200
    assert update_existing.json()["category_id"] == assigned_category["id"]

    reassign_inactive = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"category_id": other_category["id"]},
    )
    assert reassign_inactive.status_code == 409


@pytest.mark.api
def test_update_product_can_clear_category(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    product = client.post(
        "/api/v1/products",
        json={
            "sku": "UPDATE-003",
            "name": "Phone",
            "category_id": category["id"],
        },
    ).json()

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"category_id": None},
    )

    assert response.status_code == 200
    assert response.json()["category_id"] is None


@pytest.mark.api
def test_update_product_rejects_invalid_category(client):
    product = client.post(
        "/api/v1/products",
        json={"sku": "UPDATE-004", "name": "Phone"},
    ).json()

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"category_id": str(uuid4())},
    )

    assert response.status_code == 404


@pytest.mark.api
def test_update_product_rejects_duplicate_sku(client):
    client.post(
        "/api/v1/products",
        json={"sku": "EXISTING-001", "name": "First Product"},
    )

    product = client.post(
        "/api/v1/products",
        json={"sku": "EXISTING-002", "name": "Second Product"},
    ).json()

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"sku": "EXISTING-001"},
    )

    assert response.status_code == 409


@pytest.mark.api
def test_update_nonexistent_product(client):
    response = client.patch(
        "/api/v1/products/00000000-0000-0000-0000-000000000001",
        json={"name": "Updated Name"},
    )

    assert response.status_code == 404


@pytest.mark.api
def test_archive_product(client):
    product = client.post(
        "/api/v1/products",
        json={"sku": "ARCHIVE-001", "name": "Product to Archive"},
    ).json()

    updated = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Updated Product Name"},
    )
    assert updated.status_code == 200

    response = client.delete(
        f"/api/v1/products/{product['id']}",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"

    # Confirm the product still exists after archiving.
    get_response = client.get(
        f"/api/v1/products/{product['id']}",
    )

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "ARCHIVED"

    audit = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "PRODUCT", "entity_id": product["id"]},
    )
    assert audit.status_code == 200
    entries = audit.json()["items"]
    assert {entry["action"] for entry in entries} == {
        "PRODUCT_CREATED", "PRODUCT_UPDATED", "PRODUCT_ARCHIVED",
    }
    assert all(entry["admin_id"] for entry in entries)


@pytest.mark.api
def test_archive_nonexistent_product(client):
    response = client.delete(
        "/api/v1/products/00000000-0000-0000-0000-000000000001",
    )

    assert response.status_code == 404


@pytest.fixture
def client(admin_client):
    """Administrative API tests run as an authenticated super-admin."""
    return admin_client
