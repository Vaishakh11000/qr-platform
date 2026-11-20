from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models import (
    AdminUser,
    AuditLog,
    LocationPolicy,
    LocationPolicyAssignment,
    Product,
    Region,
    Role,
)


def create_admin(db, role_name="SUPER_ADMIN"):
    role = Role(
        name=role_name,
        description="Location policy test role",
    )
    db.add(role)
    db.flush()

    admin = AdminUser(
        name="Policy Test Admin",
        email=f"{uuid4().hex}@example.test",
        password_hash=hash_password("Test-Password-123!"),
        role_id=role.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()

    return admin


def admin_headers(db, role_name="SUPER_ADMIN"):
    admin = create_admin(db, role_name)
    token = create_access_token(admin.id)

    return {
        "Authorization": f"Bearer {token}"
    }, admin


def create_policy(client, headers, name="Test Location Policy"):
    response = client.post(
        "/api/v1/location-policies",
        headers=headers,
        json={
            "name": name,
            "requirement": "MANDATORY",
            "method": "GPS_REQUIRED",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_product(db):
    product = Product(
        sku=f"POLICY-{uuid4().hex[:12]}",
        name="Policy Test Product",
        status="DRAFT",
    )
    db.add(product)
    db.flush()
    return product


def create_region(db, active=True):
    region = Region(
        name="Policy Test Region",
        region_code=f"REG-{uuid4().hex[:12]}",
        region_type="TEST",
        is_active=active,
    )
    db.add(region)
    db.flush()
    return region


# Authentication

def test_policy_list_rejects_missing_authentication(client):
    response = client.get("/api/v1/location-policies")
    assert response.status_code == 401


def test_policy_creation_rejects_missing_authentication(client):
    response = client.post(
        "/api/v1/location-policies",
        json={
            "name": "Unauthorized Policy",
            "requirement": "MANDATORY",
            "method": "GPS_REQUIRED",
        },
    )
    assert response.status_code == 401


def test_policy_management_rejects_non_super_admin(client, db_session):
    headers, _ = admin_headers(db_session, "CONTENT_EDITOR")

    response = client.get(
        "/api/v1/location-policies",
        headers=headers,
    )

    assert response.status_code == 403


# Policy CRUD

def test_create_location_policy(client, db_session):
    headers, admin = admin_headers(db_session)

    data = create_policy(client, headers)

    assert data["name"] == "Test Location Policy"
    assert data["requirement"] == "MANDATORY"
    assert data["method"] == "GPS_REQUIRED"
    assert data["is_active"] is True
    assert data["created_by"] == str(admin.id)


def test_list_location_policies(client, db_session):
    headers, _ = admin_headers(db_session)

    create_policy(client, headers, "Policy One")
    create_policy(client, headers, "Policy Two")

    response = client.get(
        "/api/v1/location-policies",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {item["name"] for item in response.json()} == {
        "Policy One",
        "Policy Two",
    }

    first_page = client.get(
        "/api/v1/location-policies",
        params={"offset": 0, "limit": 1},
        headers=headers,
    )
    second_page = client.get(
        "/api/v1/location-policies",
        params={"offset": 1, "limit": 1},
        headers=headers,
    )
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()[0]["id"] != second_page.json()[0]["id"]


def test_get_location_policy(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    response = client.get(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == policy["id"]


def test_get_nonexistent_policy(client, db_session):
    headers, _ = admin_headers(db_session)

    response = client.get(
        f"/api/v1/location-policies/{uuid4()}",
        headers=headers,
    )

    assert response.status_code == 404


def test_update_location_policy(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    response = client.patch(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
        json={
            "name": "Updated Policy",
            "method": "GPS_IP_FALLBACK",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Policy"
    assert response.json()["method"] == "GPS_IP_FALLBACK"
    assert response.json()["requirement"] == "MANDATORY"


def test_deactivate_location_policy(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    response = client.delete(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_list_active_policies_filter(client, db_session):
    headers, _ = admin_headers(db_session)

    active = create_policy(client, headers, "Active Policy")
    inactive = create_policy(client, headers, "Inactive Policy")

    client.delete(
        f"/api/v1/location-policies/{inactive['id']}",
        headers=headers,
    )

    response = client.get(
        "/api/v1/location-policies",
        params={"is_active": "true"},
        headers=headers,
    )

    assert response.status_code == 200
    assert all(item["is_active"] for item in response.json())
    assert active["id"] in {
        item["id"] for item in response.json()
    }


# Assignment creation

def test_create_global_assignment(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    )

    assert response.status_code == 201
    assert response.json()["scope_type"] == "GLOBAL"
    assert response.json()["product_id"] is None
    assert response.json()["region_id"] is None


def test_create_product_assignment(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)
    product = create_product(db_session)

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "PRODUCT",
            "product_id": str(product.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["product_id"] == str(product.id)


def test_create_region_assignment(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)
    region = create_region(db_session)

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "REGION",
            "region_id": str(region.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["region_id"] == str(region.id)


def test_duplicate_global_assignment_rejected(client, db_session):
    headers, _ = admin_headers(db_session)
    first = create_policy(client, headers)
    second = create_policy(client, headers, "Second Policy")

    payload = {
        "scope_type": "GLOBAL",
        "policy_id": first["id"],
    }

    first_response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json=payload,
    )

    second_response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            **payload,
            "policy_id": second["id"],
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_assignment_rejects_nonexistent_product(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "PRODUCT",
            "product_id": str(uuid4()),
        },
    )

    assert response.status_code == 404


def test_assignment_rejects_inactive_region(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)
    region = create_region(db_session, active=False)

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "REGION",
            "region_id": str(region.id),
        },
    )

    assert response.status_code == 404


def test_assignment_rejects_inactive_policy(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    client.delete(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    )

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    )

    assert response.status_code == 409


def test_assignment_rejects_invalid_scope_combination(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
            "product_id": str(uuid4()),
        },
    )

    assert response.status_code == 422


# Assignment retrieval, replacement and deletion

def test_list_assignments_by_policy(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    )

    response = client.get(
        "/api/v1/location-policy-assignments",
        params={"policy_id": policy["id"]},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_assignment(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    created = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    ).json()

    response = client.get(
        f"/api/v1/location-policy-assignments/{created['id']}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_replace_assignment(client, db_session):
    headers, _ = admin_headers(db_session)
    first_policy = create_policy(client, headers, "First Policy")
    second_policy = create_policy(client, headers, "Second Policy")

    created = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": first_policy["id"],
            "scope_type": "GLOBAL",
        },
    ).json()

    response = client.put(
        f"/api/v1/location-policy-assignments/{created['id']}",
        headers=headers,
        json={
            "policy_id": second_policy["id"],
            "scope_type": "GLOBAL",
        },
    )

    assert response.status_code == 200
    assert response.json()["policy_id"] == second_policy["id"]


def test_delete_assignment(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers)

    created = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    ).json()

    response = client.delete(
        f"/api/v1/location-policy-assignments/{created['id']}",
        headers=headers,
    )

    assert response.status_code == 204

    lookup = client.get(
        f"/api/v1/location-policy-assignments/{created['id']}",
        headers=headers,
    )

    assert lookup.status_code == 404

# Audit logging

def test_audit_log_records_policy_creation(client, db_session):
    headers, admin = admin_headers(db_session)
    policy = create_policy(client, headers, "Audited Policy")

    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_CREATED",
        entity_id=__import__("uuid").UUID(policy["id"]),
    ).one()

    assert log.admin_id == admin.id
    assert log.entity_type == "LOCATION_POLICY"
    assert log.new_values == {
        "name": "Audited Policy",
        "requirement": "MANDATORY",
        "method": "GPS_REQUIRED",
        "is_active": True,
    }
    assert log.old_values is None


def test_audit_log_records_policy_update(client, db_session):
    headers, admin = admin_headers(db_session)
    policy = create_policy(client, headers, "Original Policy")

    response = client.patch(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
        json={
            "name": "Revised Policy",
            "method": "GPS_IP_FALLBACK",
        },
    )
    assert response.status_code == 200

    from uuid import UUID

    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_UPDATED",
        entity_id=UUID(policy["id"]),
    ).one()

    assert log.admin_id == admin.id
    assert log.old_values["name"] == "Original Policy"
    assert log.old_values["method"] == "GPS_REQUIRED"
    assert log.new_values["name"] == "Revised Policy"
    assert log.new_values["method"] == "GPS_IP_FALLBACK"


def test_audit_log_records_policy_deactivation(client, db_session):
    headers, admin = admin_headers(db_session)
    policy = create_policy(client, headers, "Policy To Deactivate")

    response = client.delete(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    )
    assert response.status_code == 200

    from uuid import UUID

    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_DEACTIVATED",
        entity_id=UUID(policy["id"]),
    ).one()

    assert log.admin_id == admin.id
    assert log.old_values["is_active"] is True
    assert log.new_values["is_active"] is False


def test_permanent_policy_delete_requires_inactive_policy(client, db_session):
    headers, _ = admin_headers(db_session)
    policy = create_policy(client, headers, "Active Policy")

    response = client.delete(
        f"/api/v1/location-policies/{policy['id']}/permanent",
        headers=headers,
    )

    assert response.status_code == 409
    assert client.get(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    ).status_code == 200


def test_permanent_policy_delete_removes_assignments_and_audits(client, db_session):
    headers, admin = admin_headers(db_session)
    policy = create_policy(client, headers, "Inactive Policy")
    assignment = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={"policy_id": policy["id"], "scope_type": "GLOBAL"},
    )
    assert assignment.status_code == 201
    deactivated = client.delete(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    )
    assert deactivated.status_code == 200

    response = client.delete(
        f"/api/v1/location-policies/{policy['id']}/permanent",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert client.get(
        f"/api/v1/location-policies/{policy['id']}",
        headers=headers,
    ).status_code == 404
    assert client.get(
        "/api/v1/location-policy-assignments",
        headers=headers,
        params={"policy_id": policy["id"]},
    ).json() == []

    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_DELETED",
        entity_id=__import__("uuid").UUID(policy["id"]),
    ).one()
    assert log.admin_id == admin.id
    assert log.old_values["assignments"][0]["scope_type"] == "GLOBAL"


def test_audit_log_records_assignment_creation(client, db_session):
    headers, admin = admin_headers(db_session)
    policy = create_policy(client, headers, "Assignment Audit Policy")

    response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    )
    assert response.status_code == 201

    from uuid import UUID

    assignment_id = UUID(response.json()["id"])
    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_ASSIGNMENT_CREATED",
        entity_id=assignment_id,
    ).one()

    assert log.admin_id == admin.id
    assert log.entity_type == "LOCATION_POLICY_ASSIGNMENT"
    assert log.old_values is None
    assert log.new_values["policy_id"] == policy["id"]
    assert log.new_values["scope_type"] == "GLOBAL"


def test_audit_log_records_assignment_replacement(client, db_session):
    headers, admin = admin_headers(db_session)
    first_policy = create_policy(client, headers, "First Audit Policy")
    second_policy = create_policy(client, headers, "Second Audit Policy")

    created = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": first_policy["id"],
            "scope_type": "GLOBAL",
        },
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]

    response = client.put(
        f"/api/v1/location-policy-assignments/{assignment_id}",
        headers=headers,
        json={
            "policy_id": second_policy["id"],
            "scope_type": "GLOBAL",
        },
    )
    assert response.status_code == 200

    from uuid import UUID

    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_ASSIGNMENT_UPDATED",
        entity_id=UUID(assignment_id),
    ).one()

    assert log.admin_id == admin.id
    assert log.old_values["policy_id"] == first_policy["id"]
    assert log.new_values["policy_id"] == second_policy["id"]


def test_audit_log_records_assignment_deletion(client, db_session):
    headers, admin = admin_headers(db_session)
    policy = create_policy(client, headers, "Deletion Audit Policy")

    created = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": policy["id"],
            "scope_type": "GLOBAL",
        },
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]

    response = client.delete(
        f"/api/v1/location-policy-assignments/{assignment_id}",
        headers=headers,
    )
    assert response.status_code == 204

    from uuid import UUID

    log = db_session.query(AuditLog).filter_by(
        action="LOCATION_POLICY_ASSIGNMENT_DELETED",
        entity_id=UUID(assignment_id),
    ).one()

    assert log.admin_id == admin.id
    assert log.old_values["policy_id"] == policy["id"]
    assert log.old_values["scope_type"] == "GLOBAL"
    assert log.new_values is None


def test_failed_duplicate_assignment_does_not_create_audit_log(
    client,
    db_session,
):
    headers, _ = admin_headers(db_session)
    first_policy = create_policy(client, headers, "First Duplicate Policy")
    second_policy = create_policy(client, headers, "Second Duplicate Policy")

    first_response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": first_policy["id"],
            "scope_type": "GLOBAL",
        },
    )
    assert first_response.status_code == 201

    action = "LOCATION_POLICY_ASSIGNMENT_CREATED"
    count_before = db_session.query(AuditLog).filter_by(
        action=action,
    ).count()

    rejected_response = client.post(
        "/api/v1/location-policy-assignments",
        headers=headers,
        json={
            "policy_id": second_policy["id"],
            "scope_type": "GLOBAL",
        },
    )

    assert rejected_response.status_code == 409

    count_after = db_session.query(AuditLog).filter_by(
        action=action,
    ).count()

    assert count_after == count_before

