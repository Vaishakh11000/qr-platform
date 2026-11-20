import pytest

from uuid import uuid4


@pytest.mark.api
def test_create_category(client):
    response = client.post(
        "/api/v1/categories",
        json={
            "name": "Electronics",
            "description": "Electronic products",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Electronics"
    assert data["description"] == "Electronic products"
    assert data["parent_id"] is None
    assert data["is_active"] is True
    assert data["id"] is not None


@pytest.mark.api
def test_create_category_with_invalid_parent(client):
    response = client.post(
        "/api/v1/categories",
        json={
            "name": "Mobile Phones",
            "parent_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent category not found."


@pytest.mark.api
def test_create_category_rejects_empty_name(client):
    response = client.post(
        "/api/v1/categories",
        json={"name": "   "},
    )

    assert response.status_code == 422


@pytest.mark.api
def test_create_category_rejects_missing_name(client):
    response = client.post(
        "/api/v1/categories",
        json={
            "description": "Category without a name",
        },
    )

    assert response.status_code == 422


@pytest.mark.api
def test_list_categories(client):
    client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    )

    client.post(
        "/api/v1/categories",
        json={"name": "Furniture"},
    )

    response = client.get("/api/v1/categories")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["name"] for item in data} == {
        "Electronics",
        "Furniture",
    }


@pytest.mark.api
def test_list_categories_with_pagination(client):
    for name in ["Category A", "Category B", "Category C"]:
        client.post(
            "/api/v1/categories",
            json={"name": name},
        )

    response = client.get(
        "/api/v1/categories",
        params={"offset": 1, "limit": 1},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Category B"


@pytest.mark.api
def test_list_categories_by_parent(client):
    parent_response = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    )

    parent_id = parent_response.json()["id"]

    client.post(
        "/api/v1/categories",
        json={
            "name": "Mobile Phones",
            "parent_id": parent_id,
        },
    )

    client.post(
        "/api/v1/categories",
        json={"name": "Furniture"},
    )

    response = client.get(
        "/api/v1/categories",
        params={"parent_id": parent_id},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Mobile Phones"


@pytest.mark.api
def test_get_category_by_id(client):
    create_response = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    )

    category_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/categories/{category_id}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == category_id
    assert response.json()["name"] == "Electronics"


@pytest.mark.api
def test_get_nonexistent_category(client):
    response = client.get(
        "/api/v1/categories/00000000-0000-0000-0000-000000000001"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found."


@pytest.mark.api
def test_update_category_name(client):
    create_response = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    )

    category_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/categories/{category_id}",
        json={"name": "Consumer Electronics"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Consumer Electronics"


@pytest.mark.api
def test_update_category_parent(client):
    parent = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    child = client.post(
        "/api/v1/categories",
        json={"name": "Mobile Phones"},
    ).json()

    response = client.patch(
        f"/api/v1/categories/{child['id']}",
        json={"parent_id": parent["id"]},
    )

    assert response.status_code == 200
    assert response.json()["parent_id"] == parent["id"]


@pytest.mark.api
def test_update_category_rejects_invalid_parent(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    response = client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"parent_id": str(uuid4())},
    )

    assert response.status_code == 404


@pytest.mark.api
def test_update_category_rejects_hierarchy_cycle(client):
    parent = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    child = client.post(
        "/api/v1/categories",
        json={
            "name": "Mobile Phones",
            "parent_id": parent["id"],
        },
    ).json()

    response = client.patch(
        f"/api/v1/categories/{parent['id']}",
        json={"parent_id": child["id"]},
    )

    assert response.status_code == 409


@pytest.mark.api
def test_deactivate_category(client):
    category = client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
    ).json()

    response = client.delete(
        f"/api/v1/categories/{category['id']}"
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Verify that the category still exists.
    get_response = client.get(
        f"/api/v1/categories/{category['id']}"
    )

    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False

    reactivated = client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True

    audit = client.get(
        "/api/v1/audit-logs",
        params={
            "entity_type": "PRODUCT_CATEGORY",
            "entity_id": category["id"],
        },
    )
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()["items"]}
    assert actions == {"CATEGORY_CREATED", "CATEGORY_DEACTIVATED", "CATEGORY_REACTIVATED"}


@pytest.mark.api
def test_deactivate_nonexistent_category(client):
    response = client.delete(
        "/api/v1/categories/00000000-0000-0000-0000-000000000001"
    )

    assert response.status_code == 404


@pytest.fixture
def client(admin_client):
    """Administrative API tests run as an authenticated super-admin."""
    return admin_client
