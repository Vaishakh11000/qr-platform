import pytest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from uuid import uuid4
from pydantic import ValidationError

from app.schemas.forms import FormAssignmentCreate, FormSchema
from app.services.form_service import (
    InvalidFormAnswers,
    _validated_form_answers,
    create_form_assignment,
    select_effective_form_assignment,
)


def test_form_schema_rejects_duplicate_field_keys():
    with pytest.raises(ValidationError):
        FormSchema.model_validate({
            "fields": [
                {"key": "email", "label": "Email", "type": "EMAIL"},
                {"key": "email", "label": "Again", "type": "TEXT"},
            ]
        })


def test_form_answers_validate_required_fields_and_select_options():
    schema = {
        "fields": [
            {"key": "email", "label": "Email", "type": "EMAIL", "required": True},
            {"key": "interest", "label": "Interest", "type": "SELECT", "options": ["Quote", "Support"]},
        ]
    }
    assert _validated_form_answers(schema, {"email": " customer@example.com ", "interest": "Quote"}) == {
        "email": "customer@example.com",
        "interest": "Quote",
    }
    with pytest.raises(InvalidFormAnswers):
        _validated_form_answers(schema, {"email": "invalid-email", "interest": "Other"})


def test_form_answers_reject_unknown_keys_and_wrong_types():
    schema = {"fields": [{"key": "consent", "label": "Consent", "type": "CHECKBOX", "required": True}]}
    with pytest.raises(InvalidFormAnswers):
        _validated_form_answers(schema, {"consent": "yes"})
    with pytest.raises(InvalidFormAnswers):
        _validated_form_answers(schema, {"consent": True, "unexpected": "value"})


def test_phone_answers_accept_international_format_and_reject_invalid_numbers():
    schema = {"fields": [{"key": "phone", "label": "Phone number", "type": "PHONE", "required": True}]}
    assert _validated_form_answers(schema, {"phone": " +91 (987) 654-3210 "}) == {
        "phone": "+91 (987) 654-3210",
    }
    with pytest.raises(InvalidFormAnswers):
        _validated_form_answers(schema, {"phone": "call me at 9876543210"})
    with pytest.raises(InvalidFormAnswers):
        _validated_form_answers(schema, {"phone": "1234"})


def test_form_assignment_requires_matching_target_scope():
    with pytest.raises(ValidationError):
        FormAssignmentCreate.model_validate({
            "form_version_id": "00000000-0000-0000-0000-000000000001",
            "scope_type": "GLOBAL",
            "product_id": "00000000-0000-0000-0000-000000000002",
        })


def test_form_resolution_keeps_distinct_forms_and_resolves_overlapping_scopes():
    now = datetime.now(timezone.utc)
    region_assignment = SimpleNamespace(scope_type="REGION", created_at=now)
    product_assignment = SimpleNamespace(scope_type="PRODUCT", created_at=now + timedelta(seconds=1))
    global_assignment = SimpleNamespace(scope_type="GLOBAL", created_at=now + timedelta(seconds=2))
    version = SimpleNamespace()
    enquiry_form = SimpleNamespace(id="enquiry")
    registration_form = SimpleNamespace(id="registration")
    region_enquiry = (region_assignment, version, enquiry_form)
    product_enquiry = (product_assignment, version, enquiry_form)
    global_registration = (global_assignment, version, registration_form)

    selected = select_effective_form_assignment([global_registration, product_enquiry, region_enquiry])
    assert selected == [region_enquiry, global_registration]


def test_form_resolution_prefers_closest_region_in_hierarchy():
    now = datetime.now(timezone.utc)
    parent_id = "parent-region"
    child_id = "child-region"
    parent_assignment = SimpleNamespace(
        scope_type="REGION", region_id=parent_id, created_at=now + timedelta(seconds=5)
    )
    child_assignment = SimpleNamespace(
        scope_type="REGION", region_id=child_id, created_at=now
    )
    form = SimpleNamespace(id="enquiry")
    parent_match = (parent_assignment, SimpleNamespace(), form)
    child_match = (child_assignment, SimpleNamespace(), form)

    selected = select_effective_form_assignment(
        [parent_match, child_match],
        {child_id: 0, parent_id: 1},
    )

    assert selected == [child_match]


def test_assigning_form_deactivates_previous_same_scope_assignment_and_keeps_history():
    version_id = "00000000-0000-0000-0000-000000000001"
    form_id = "00000000-0000-0000-0000-000000000002"
    previous = SimpleNamespace(id=uuid4(), is_active=True)
    form = SimpleNamespace(id=form_id, status="ACTIVE")
    version = SimpleNamespace(id=version_id, form_id=form_id, published_at=now_utc())

    class FakeResult:
        def scalar_one_or_none(self):
            return form

        def scalars(self):
            return self

        def all(self):
            return [previous]

    class FakeSession:
        def __init__(self):
            self.added = []
            self.execute_count = 0

        def get(self, model, _identity):
            return version if model.__name__ == "FormVersion" else None

        def execute(self, _statement):
            self.execute_count += 1
            return FakeResult()

        def scalars(self, _statement):
            return FakeResult()

        def add(self, item):
            self.added.append(item)

        def flush(self):
            for item in self.added:
                if getattr(item, "id", None) is None:
                    item.id = uuid4()

        def commit(self):
            pass

        def refresh(self, _item):
            pass

    db = FakeSession()
    created = create_form_assignment(
        db,
        FormAssignmentCreate(
            form_version_id=version_id,
            scope_type="GLOBAL",
            requirement="OPTIONAL",
        ),
    )

    assert previous.is_active is False
    assert created.is_active is True
    assert created in db.added


def now_utc():
    return datetime.now(timezone.utc)
