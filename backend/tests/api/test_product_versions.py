import pytest

from uuid import uuid4


def create_product(client):
    return client.post(
        "/api/v1/products",
        json={
            "sku": f"VERSION-{uuid4().hex[:12]}",
            "name": "Version Test Product",
        },
    ).json()


def create_version(client, product_id, content=None):
    if content is None:
        content = {"title": "Initial product information"}

    return client.post(
        f"/api/v1/products/{product_id}/versions",
        json={"content_snapshot": content},
    )


@pytest.mark.api
def test_create_product_version(client):
    product = create_product(client)

    response = create_version(client, product["id"])

    assert response.status_code == 201

    data = response.json()

    assert data["product_id"] == product["id"]
    assert data["version_number"] == 1
    assert data["status"] == "DRAFT"
    assert data["content_snapshot"]["title"] == "Initial product information"
    assert data["published_at"] is None


@pytest.mark.api
def test_create_product_version_increments_version_number(client):
    product = create_product(client)

    first = create_version(client, product["id"])
    second = create_version(
        client,
        product["id"],
        {"title": "Second version"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["version_number"] == 1
    assert second.json()["version_number"] == 2


@pytest.mark.api
def test_create_version_for_nonexistent_product(client):
    response = create_version(
        client,
        "00000000-0000-0000-0000-000000000001",
    )

    assert response.status_code == 404


@pytest.mark.api
def test_cannot_create_version_for_archived_product(client):
    product = create_product(client)

    client.delete(f"/api/v1/products/{product['id']}")

    response = create_version(client, product["id"])

    assert response.status_code == 409


@pytest.mark.api
def test_list_product_versions(client):
    product = create_product(client)

    create_version(client, product["id"])
    create_version(client, product["id"], {"title": "Second"})
    create_version(client, product["id"], {"title": "Third"})

    response = client.get(
        f"/api/v1/products/{product['id']}/versions",
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 3
    assert [item["version_number"] for item in data] == [3, 2, 1]


@pytest.mark.api
def test_list_versions_for_nonexistent_product(client):
    response = client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000001/versions",
    )

    assert response.status_code == 404


@pytest.mark.api
def test_get_product_version(client):
    product = create_product(client)
    version = create_version(client, product["id"]).json()

    response = client.get(
        f"/api/v1/products/{product['id']}/versions/{version['id']}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == version["id"]


@pytest.mark.api
def test_get_nonexistent_product_version(client):
    product = create_product(client)

    response = client.get(
        f"/api/v1/products/{product['id']}/versions/"
        "00000000-0000-0000-0000-000000000001",
    )

    assert response.status_code == 404


@pytest.mark.api
def test_update_draft_product_version(client):
    product = create_product(client)
    version = create_version(client, product["id"]).json()

    response = client.patch(
        f"/api/v1/products/{product['id']}/versions/{version['id']}",
        json={
            "content_snapshot": {
                "title": "Updated product",
                "description": "Updated description",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["content_snapshot"]["title"] == "Updated product"
    assert (
        response.json()["content_snapshot"]["description"]
        == "Updated description"
    )

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "PRODUCT_VERSION", "entity_id": version["id"]},
    )
    assert audits.status_code == 200
    assert {item["action"] for item in audits.json()["items"]} == {
        "PRODUCT_VERSION_CREATED", "PRODUCT_VERSION_UPDATED",
    }
    assert all("content_sha256" in item["new_values"] for item in audits.json()["items"])


@pytest.mark.api
def test_update_nonexistent_version(client):
    product = create_product(client)

    response = client.patch(
        f"/api/v1/products/{product['id']}/versions/"
        "00000000-0000-0000-0000-000000000001",
        json={"content_snapshot": {"title": "Updated"}},
    )

    assert response.status_code == 404


@pytest.mark.api
def test_update_published_version_is_rejected(client):
    product = create_product(client)
    version = create_version(client, product["id"]).json()

    publish_response = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{version['id']}/publish",
    )

    assert publish_response.status_code == 200

    update_response = client.patch(
        f"/api/v1/products/{product['id']}/versions/{version['id']}",
        json={"content_snapshot": {"title": "Changed after publishing"}},
    )

    assert update_response.status_code == 409


@pytest.mark.api
def test_publish_product_version(client):
    product = create_product(client)
    version = create_version(client, product["id"]).json()

    response = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{version['id']}/publish",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "PUBLISHED"
    assert data["published_at"] is not None

    product_response = client.get(
        f"/api/v1/products/{product['id']}",
    )

    assert product_response.status_code == 200
    assert product_response.json()["status"] == "ACTIVE"

    audits = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "PRODUCT_VERSION", "entity_id": version["id"]},
    )
    assert audits.status_code == 200
    actions = {item["action"] for item in audits.json()["items"]}
    assert actions == {"PRODUCT_VERSION_CREATED", "PRODUCT_VERSION_PUBLISHED"}
    assert all(item["admin_id"] for item in audits.json()["items"])


@pytest.mark.api
def test_publishing_second_version_retires_first(client):
    product = create_product(client)

    first = create_version(client, product["id"]).json()

    first_publish = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{first['id']}/publish",
    )

    assert first_publish.status_code == 200

    second = create_version(
        client,
        product["id"],
        {"title": "Updated information"},
    ).json()

    second_publish = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{second['id']}/publish",
    )

    assert second_publish.status_code == 200
    assert second_publish.json()["status"] == "PUBLISHED"

    versions = client.get(
        f"/api/v1/products/{product['id']}/versions",
    ).json()

    versions_by_number = {
        version["version_number"]: version
        for version in versions
    }

    assert versions_by_number[1]["status"] == "RETIRED"
    assert versions_by_number[1]["published_at"] is not None
    assert versions_by_number[2]["status"] == "PUBLISHED"


@pytest.mark.api
def test_cannot_publish_version_twice(client):
    product = create_product(client)
    version = create_version(client, product["id"]).json()

    first = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{version['id']}/publish",
    )

    second = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{version['id']}/publish",
    )

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.api
def test_publish_nonexistent_version(client):
    product = create_product(client)

    response = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        "00000000-0000-0000-0000-000000000001/publish",
    )

    assert response.status_code == 404


@pytest.mark.api
def test_cannot_publish_version_for_archived_product(client):
    product = create_product(client)
    version = create_version(client, product["id"]).json()

    client.delete(f"/api/v1/products/{product['id']}")

    response = client.post(
        f"/api/v1/products/{product['id']}/versions/"
        f"{version['id']}/publish",
    )

    assert response.status_code == 409


@pytest.fixture
def client(admin_client):
    """Administrative API tests run as an authenticated super-admin."""
    return admin_client
