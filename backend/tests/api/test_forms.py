from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import (
    AuditLog,
    Product,
    ProductVersion,
    QRAllocation,
    QRBatch,
    QRCode,
    Region,
)


def sample_schema(label="Email address"):
    return {
        "fields": [{
            "key": "email",
            "label": label,
            "type": "EMAIL",
            "required": True,
        }]
    }


def create_form(admin_client, *, name="Customer enquiry", schema=None):
    response = admin_client.post(
        "/api/v1/forms",
        json={
            "name": name,
            "description": "Request more product information.",
            "schema": schema or sample_schema(),
        },
    )
    assert response.status_code == 201
    return response.json()


def create_allowed_scan(client, db_session):
    product = Product(
        sku=f"FORM-{uuid4().hex[:12]}",
        name="Form workflow product",
        status="ACTIVE",
    )
    region = Region(
        name=f"Form region {uuid4().hex[:8]}",
        region_code=f"FORM-{uuid4().hex[:8]}",
        region_type="TEST",
        is_active=True,
    )
    db_session.add_all([product, region])
    db_session.flush()

    version = ProductVersion(
        product_id=product.id,
        version_number=1,
        content_snapshot={"title": product.name},
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(version)
    db_session.flush()
    product.current_version_id = version.id

    batch = QRBatch(
        batch_code=f"FORM-{uuid4().hex}",
        quantity=1,
        generation_status="GENERATED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()

    code = QRCode(
        batch_id=batch.id,
        token=f"form-test-{uuid4().hex}",
        status="ACTIVE",
    )
    db_session.add(code)
    db_session.flush()
    db_session.add(QRAllocation(
        qr_code_id=code.id,
        product_id=product.id,
        region_id=region.id,
    ))
    db_session.flush()

    started = client.post("/api/v1/public/scans/start", json={"token": code.token})
    assert started.status_code == 201
    assert started.json()["location_requested"] is False

    completed = client.post(
        f"/api/v1/public/scans/{started.json()['scan_id']}/location",
        json={"location_status": "SKIPPED"},
    )
    assert completed.status_code == 200
    assert completed.json()["result_status"] == "ALLOWED"
    return started.json()["scan_id"]


@pytest.mark.api
def test_form_versions_assignments_and_admin_changes_are_audited(admin_client, db_session):
    created = create_form(admin_client)
    form_id = created["form"]["id"]
    first_version = created["version"]

    created_audit = db_session.query(AuditLog).filter_by(
        action="FORM_CREATED",
        entity_id=form_id,
    ).one()
    assert created_audit.admin_id is not None
    assert created_audit.new_values["field_count"] == 1
    assert "schema_sha256" in created_audit.new_values
    assert "schema" not in created_audit.new_values

    version_response = admin_client.post(
        f"/api/v1/forms/{form_id}/versions",
        json={"schema": sample_schema("Business email")},
    )
    assert version_response.status_code == 201
    second_version = version_response.json()
    assert second_version["version_number"] == 2

    update_response = admin_client.patch(
        f"/api/v1/forms/{form_id}/versions/{second_version['id']}",
        json={"schema": sample_schema("Work email")},
    )
    assert update_response.status_code == 200

    publish_response = admin_client.post(
        f"/api/v1/forms/{form_id}/versions/{second_version['id']}/publish"
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["published_at"] is not None

    assignment_response = admin_client.post(
        "/api/v1/forms/assignments",
        json={
            "form_version_id": second_version["id"],
            "scope_type": "GLOBAL",
            "requirement": "MANDATORY",
        },
    )
    assert assignment_response.status_code == 201
    assignment = assignment_response.json()

    update_assignment_response = admin_client.patch(
        f"/api/v1/forms/assignments/{assignment['id']}",
        json={"requirement": "OPTIONAL", "is_active": False},
    )
    assert update_assignment_response.status_code == 200
    assert update_assignment_response.json()["is_active"] is False

    expected_actions = {
        "FORM_CREATED",
        "FORM_VERSION_CREATED",
        "FORM_VERSION_UPDATED",
        "FORM_VERSION_PUBLISHED",
        "FORM_ASSIGNMENT_CREATED",
        "FORM_ASSIGNMENT_UPDATED",
    }
    events = db_session.query(AuditLog).filter(
        AuditLog.entity_id.in_([form_id, first_version["id"], second_version["id"], assignment["id"]])
    ).all()
    assert expected_actions <= {event.action for event in events}
    assert all(event.admin_id for event in events)
    assert all("Work email" not in str(event.new_values) for event in events)
    assert all("Business email" not in str(event.new_values) for event in events)


@pytest.mark.api
def test_replacing_same_scope_form_assignment_audits_both_assignments(admin_client, db_session):
    created = create_form(admin_client)
    form_id = created["form"]["id"]
    first_version = created["version"]
    assert admin_client.post(
        f"/api/v1/forms/{form_id}/versions/{first_version['id']}/publish"
    ).status_code == 200

    first = admin_client.post(
        "/api/v1/forms/assignments",
        json={"form_version_id": first_version["id"], "scope_type": "GLOBAL"},
    )
    assert first.status_code == 201
    first_assignment_id = first.json()["id"]

    next_version = admin_client.post(
        f"/api/v1/forms/{form_id}/versions",
        json={"schema": sample_schema("Updated email")},
    )
    assert next_version.status_code == 201
    assert admin_client.post(
        f"/api/v1/forms/{form_id}/versions/{next_version.json()['id']}/publish"
    ).status_code == 200

    replacement = admin_client.post(
        "/api/v1/forms/assignments",
        json={"form_version_id": next_version.json()["id"], "scope_type": "GLOBAL"},
    )
    assert replacement.status_code == 201

    old_assignment_audit = db_session.query(AuditLog).filter_by(
        action="FORM_ASSIGNMENT_DEACTIVATED",
        entity_id=first_assignment_id,
    ).one()
    new_assignment_audit = db_session.query(AuditLog).filter_by(
        action="FORM_ASSIGNMENT_CREATED",
        entity_id=replacement.json()["id"],
    ).one()
    assert old_assignment_audit.admin_id is not None
    assert old_assignment_audit.new_values["replaced_by_assignment_id"] == replacement.json()["id"]
    assert new_assignment_audit.admin_id == old_assignment_audit.admin_id


@pytest.mark.api
def test_public_form_submission_flow_and_answer_data_is_not_audited(
    admin_client,
    client,
    db_session,
):
    scan_id = create_allowed_scan(client, db_session)
    created = create_form(admin_client)
    form_id = created["form"]["id"]
    version = created["version"]
    assert admin_client.post(
        f"/api/v1/forms/{form_id}/versions/{version['id']}/publish"
    ).status_code == 200

    assignment = admin_client.post(
        "/api/v1/forms/assignments",
        json={
            "form_version_id": version["id"],
            "scope_type": "GLOBAL",
            "requirement": "MANDATORY",
        },
    )
    assert assignment.status_code == 201
    assignment_id = assignment.json()["id"]

    forms = client.get(f"/api/v1/public/scans/{scan_id}/forms")
    assert forms.status_code == 200
    assert len(forms.json()) == 1
    assert forms.json()[0]["id"] == assignment_id
    assert forms.json()[0]["requirement"] == "MANDATORY"

    invalid = client.post(
        f"/api/v1/public/scans/{scan_id}/forms/{assignment_id}",
        json={"answers": {}},
    )
    assert invalid.status_code == 422

    answer = "customer@example.test"
    submitted = client.post(
        f"/api/v1/public/scans/{scan_id}/forms/{assignment_id}",
        json={"answers": {"email": answer}},
    )
    assert submitted.status_code == 201

    duplicate = client.post(
        f"/api/v1/public/scans/{scan_id}/forms/{assignment_id}",
        json={"answers": {"email": answer}},
    )
    assert duplicate.status_code == 409

    submissions = admin_client.get(f"/api/v1/forms/{form_id}/submissions")
    assert submissions.status_code == 200
    page = submissions.json()
    assert page["total"] == 1
    assert page["offset"] == 0
    assert page["limit"] == 50
    assert page["items"][0]["answers"] == {"email": answer}

    next_page = admin_client.get(
        f"/api/v1/forms/{form_id}/submissions",
        params={"offset": 1, "limit": 1},
    )
    assert next_page.status_code == 200
    assert next_page.json()["items"] == []
    assert next_page.json()["total"] == 1

    invalid_page = admin_client.get(
        f"/api/v1/forms/{form_id}/submissions",
        params={"limit": 101},
    )
    assert invalid_page.status_code == 422

    events = db_session.query(AuditLog).all()
    assert all(answer not in str(event.old_values) for event in events)
    assert all(answer not in str(event.new_values) for event in events)


@pytest.mark.api
def test_form_assignment_requires_published_version(admin_client):
    created = create_form(admin_client)
    response = admin_client.post(
        "/api/v1/forms/assignments",
        json={
            "form_version_id": created["version"]["id"],
            "scope_type": "GLOBAL",
        },
    )
    assert response.status_code == 409
