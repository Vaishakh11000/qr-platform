from uuid import uuid4

from app.models import Region


def create_region(client, *, parent_id=None, name="Test Region"):
    response = client.post(
        "/api/v1/regions",
        json={
            "name": name,
            "region_code": f"REG-{uuid4().hex[:12]}",
            "region_type": "TEST",
            "parent_id": str(parent_id) if parent_id else None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_region_management_requires_super_admin(client, db_session):
    from app.core.security import create_access_token, hash_password
    from app.models import AdminUser, Role

    role = Role(name="CONTENT_EDITOR", description="Region test role")
    db_session.add(role)
    db_session.flush()
    admin = AdminUser(
        name="Region Test Editor",
        email=f"{uuid4().hex}@example.test",
        password_hash=hash_password("Test-Password-123!"),
        role_id=role.id,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    response = client.get(
        "/api/v1/regions",
        headers={"Authorization": f"Bearer {create_access_token(admin.id)}"},
    )
    assert response.status_code == 403


def test_region_management_rejects_missing_authentication(client):
    response = client.get("/api/v1/regions")
    assert response.status_code == 401


def test_create_list_get_and_update_region(admin_client):
    parent = create_region(admin_client, name="Parent")
    child = create_region(
        admin_client,
        parent_id=parent["id"],
        name="Child",
    )

    listed = admin_client.get(
        "/api/v1/regions",
        params={"parent_id": parent["id"]},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [child["id"]]

    fetched = admin_client.get(f"/api/v1/regions/{child['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["parent_id"] == parent["id"]

    updated = admin_client.patch(
        f"/api/v1/regions/{child['id']}",
        json={"name": "Updated Child"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Child"

    audits = admin_client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "REGION", "entity_id": child["id"]},
    )
    assert audits.status_code == 200
    assert {item["action"] for item in audits.json()["items"]} == {
        "REGION_CREATED", "REGION_UPDATED",
    }
    assert all(item["admin_id"] for item in audits.json()["items"])


def test_create_rejects_missing_or_inactive_parent(admin_client, db_session):
    missing = admin_client.post(
        "/api/v1/regions",
        json={
            "name": "Orphan",
            "region_code": f"REG-{uuid4().hex[:12]}",
            "region_type": "TEST",
            "parent_id": str(uuid4()),
        },
    )
    assert missing.status_code == 404

    inactive_parent = Region(
        name="Inactive Parent",
        region_code=f"REG-{uuid4().hex[:12]}",
        region_type="TEST",
        is_active=False,
    )
    db_session.add(inactive_parent)
    db_session.flush()
    inactive = admin_client.post(
        "/api/v1/regions",
        json={
            "name": "Invalid Child",
            "region_code": f"REG-{uuid4().hex[:12]}",
            "region_type": "TEST",
            "parent_id": str(inactive_parent.id),
        },
    )
    assert inactive.status_code == 409


def test_update_rejects_hierarchy_cycle(admin_client):
    parent = create_region(admin_client, name="Cycle Parent")
    child = create_region(
        admin_client,
        parent_id=parent["id"],
        name="Cycle Child",
    )

    response = admin_client.patch(
        f"/api/v1/regions/{parent['id']}",
        json={"parent_id": child["id"]},
    )
    assert response.status_code == 409


def test_deactivate_region_with_active_child_is_rejected(admin_client):
    parent = create_region(admin_client, name="Protected Parent")
    create_region(
        admin_client,
        parent_id=parent["id"],
        name="Active Child",
    )

    response = admin_client.delete(f"/api/v1/regions/{parent['id']}")
    assert response.status_code == 409


def test_deactivate_region_with_only_inactive_children(admin_client):
    parent = create_region(admin_client, name="Deactivatable Parent")
    child = create_region(
        admin_client,
        parent_id=parent["id"],
        name="Inactive Child",
    )
    deactivated_child = admin_client.delete(
        f"/api/v1/regions/{child['id']}"
    )
    assert deactivated_child.status_code == 200

    deactivated_parent = admin_client.delete(
        f"/api/v1/regions/{parent['id']}"
    )
    assert deactivated_parent.status_code == 200
    assert deactivated_parent.json()["is_active"] is False


def test_reactivate_region_rejects_inactive_parent(admin_client):
    parent = create_region(admin_client, name="Inactive Parent")
    child = create_region(
        admin_client,
        parent_id=parent["id"],
        name="Inactive Child",
    )
    assert admin_client.delete(f"/api/v1/regions/{child['id']}").status_code == 200
    assert admin_client.delete(f"/api/v1/regions/{parent['id']}").status_code == 200

    response = admin_client.patch(
        f"/api/v1/regions/{child['id']}",
        json={"is_active": True},
    )
    assert response.status_code == 409


def test_region_boundary_api_persists_geometry_for_gps_detection(admin_client, db_session):
    from app.services.region_detection_service import detect_region

    region = create_region(admin_client, name="Boundary Enabled Region")
    initial = admin_client.get(f"/api/v1/regions/{region['id']}/boundary")
    assert initial.status_code == 200
    assert initial.json()["geometry"] is None

    geometry = {
        "type": "Polygon",
        "coordinates": [[[72.8, 18.9], [73.0, 18.9], [73.0, 19.1], [72.8, 19.1], [72.8, 18.9]]],
    }

    saved = admin_client.put(
        f"/api/v1/regions/{region['id']}/boundary",
        json={"geometry": geometry},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["geometry"]["type"] == "MultiPolygon"

    detected = detect_region(db_session, latitude=19.0, longitude=72.9)
    assert detected is not None
    assert str(detected.id) == region["id"]

    fetched = admin_client.get(f"/api/v1/regions/{region['id']}/boundary")
    assert fetched.status_code == 200
    assert fetched.json()["geometry"]["type"] == "MultiPolygon"

    moved_geometry = {
        "type": "Polygon",
        "coordinates": [[[73.4, 18.9], [73.6, 18.9], [73.6, 19.1], [73.4, 19.1], [73.4, 18.9]]],
    }
    updated = admin_client.put(
        f"/api/v1/regions/{region['id']}/boundary",
        json={"geometry": moved_geometry},
    )
    assert updated.status_code == 200
    assert detect_region(db_session, latitude=19.0, longitude=72.9) is None
    assert detect_region(db_session, latitude=19.0, longitude=73.5).id == detected.id

    audits = admin_client.get(
        "/api/v1/audit-logs",
        params={"action": "REGION_BOUNDARY_CREATED"},
    )
    assert audits.status_code == 200
    assert audits.json()["total"] == 1
    updates = admin_client.get(
        "/api/v1/audit-logs",
        params={"action": "REGION_BOUNDARY_UPDATED"},
    )
    assert updates.status_code == 200
    assert updates.json()["total"] == 1

    deleted = admin_client.delete(f"/api/v1/regions/{region['id']}/boundary")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert detect_region(db_session, latitude=19.0, longitude=72.9) is None


def test_region_boundary_rejects_invalid_or_out_of_range_geojson(admin_client):
    region = create_region(admin_client, name="Invalid Boundary Region")
    invalid_geometries = [
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[[-181, 0], [-180, 0], [-180, 1], [-181, 0]]]},
        {"type": "Polygon", "coordinates": [[['west', 0], ['east', 0], ['east', 1], ['west', 0]]]},
    ]
    for geometry in invalid_geometries:
        response = admin_client.put(
            f"/api/v1/regions/{region['id']}/boundary",
            json={"geometry": geometry},
        )
        assert response.status_code == 422


def test_region_boundary_routes_require_authentication(client):
    region_id = "00000000-0000-0000-0000-000000000001"
    assert client.get(f"/api/v1/regions/{region_id}/boundary").status_code == 401
