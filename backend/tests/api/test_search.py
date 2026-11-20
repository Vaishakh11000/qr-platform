import pytest
from uuid import uuid4


@pytest.mark.api
def test_global_search_returns_matching_products_and_categories(admin_client):
    category = admin_client.post(
        "/api/v1/categories",
        json={"name": "Searchable Components"},
    )
    assert category.status_code == 201

    product = admin_client.post(
        "/api/v1/products",
        json={
            "sku": "SEARCH-PUMP-01",
            "name": "Searchable Pump",
            "category_id": category.json()["id"],
        },
    )
    assert product.status_code == 201

    response = admin_client.get("/api/v1/search", params={"q": "Searchable"})

    assert response.status_code == 200
    results = response.json()["items"]
    assert {item["kind"] for item in results} >= {"Product", "Category"}
    assert any(item["title"] == "Searchable Pump" and item["page"] == "Products" for item in results)
    assert any(item["title"] == "Searchable Components" and item["page"] == "Categories" for item in results)


@pytest.mark.api
def test_global_search_finds_products_by_short_description(admin_client):
    product = admin_client.post(
        "/api/v1/products",
        json={
            "sku": "SEARCH-DESCRIPTION-01",
            "name": "Industrial Pump",
            "short_description": "Ceramic-coated impeller assembly",
        },
    )
    assert product.status_code == 201

    response = admin_client.get(
        "/api/v1/search", params={"q": "Ceramic-coated"}
    )

    assert response.status_code == 200
    assert any(
        item["id"] == product.json()["id"] and item["title"] == "Industrial Pump"
        for item in response.json()["items"]
    )


@pytest.mark.api
def test_global_search_finds_current_product_specifications(admin_client):
    product = admin_client.post(
        "/api/v1/products",
        json={"sku": "SEARCH-SPEC-01", "name": "Specification Pump"},
    )
    assert product.status_code == 201
    product_id = product.json()["id"]

    version = admin_client.post(
        f"/api/v1/products/{product_id}/versions",
        json={
            "content_snapshot": {
                "name": "Specification Pump",
                "specifications": {"Model": "AX-SEARCH-42", "Net weight": "123 kg"},
            }
        },
    )
    assert version.status_code == 201

    draft_search = admin_client.get(
        "/api/v1/search", params={"q": "AX-SEARCH-42"}
    )
    assert not any(item["id"] == product_id for item in draft_search.json()["items"])

    publish = admin_client.post(
        f"/api/v1/products/{product_id}/versions/{version.json()['id']}/publish"
    )
    assert publish.status_code == 200

    response = admin_client.get("/api/v1/search", params={"q": "AX-SEARCH-42"})
    assert response.status_code == 200
    assert any(
        item["id"] == product_id and item["title"] == "Specification Pump"
        for item in response.json()["items"]
    )


@pytest.mark.api
def test_global_search_requires_at_least_two_characters(admin_client):
    response = admin_client.get("/api/v1/search", params={"q": "a"})

    assert response.status_code == 422


@pytest.mark.api
def test_global_search_requires_authentication(client):
    response = client.get("/api/v1/search", params={"q": "products"})

    assert response.status_code == 401


@pytest.mark.api
def test_global_search_covers_regions_qr_policies_forms_and_audit_events(admin_client):
    suffix = uuid4().hex[:10]
    region_name = f"FIND-REGION-{suffix}"
    region = admin_client.post(
        "/api/v1/regions",
        json={
            "name": region_name,
            "region_code": f"FIND-{suffix}",
            "region_type": "TEST",
        },
    )
    assert region.status_code == 201

    batch = admin_client.post("/api/v1/qr/batches", json={"quantity": 1})
    assert batch.status_code == 201
    code = admin_client.get(
        f"/api/v1/qr/batches/{batch.json()['id']}/codes"
    ).json()[0]

    policy_name = f"FIND-POLICY-{suffix}"
    policy = admin_client.post(
        "/api/v1/location-policies",
        json={
            "name": policy_name,
            "requirement": "SKIPPABLE",
            "method": "GPS_REQUIRED",
        },
    )
    assert policy.status_code == 201

    form_name = f"FIND-FORM-{suffix}"
    form = admin_client.post(
        "/api/v1/forms",
        json={
            "name": form_name,
            "schema": {
                "fields": [{
                    "key": "email",
                    "label": "Email",
                    "type": "EMAIL",
                    "required": True,
                }]
            },
        },
    )
    assert form.status_code == 201

    cases = [
        (region_name, "Region"),
        (batch.json()["batch_code"], "QR batch"),
        (code["token"], "QR code"),
        (policy_name, "Location policy"),
        (form_name, "Form"),
        ("FORM_CREATED", "Audit event"),
    ]
    for query, expected_kind in cases:
        response = admin_client.get("/api/v1/search", params={"q": query})
        assert response.status_code == 200
        assert any(item["kind"] == expected_kind for item in response.json()["items"]), (
            query,
            response.json(),
        )


@pytest.mark.api
def test_global_search_finds_administration_settings_and_navigation_targets(admin_client):
    cases = [
        ("public qr", "Public QR address", "public-qr-address"),
        ("gps", "GPS collection settings", "integration-gps"),
        ("ip", "IP geolocation integration", "integration-ip-geolocation"),
        ("email", "Email and push delivery", "integration-email-push"),
        ("media", "Product media storage", "integration-media-storage"),
        ("administrator", "Administrator access", "administrators"),
    ]
    for query, title, target_key in cases:
        response = admin_client.get("/api/v1/search", params={"q": query})
        assert response.status_code == 200
        assert any(
            item["kind"] == "Setting"
            and item["title"] == title
            and item["page"] == "Administration"
            and item["target_key"] == target_key
            for item in response.json()["items"]
        ), (query, response.json())
