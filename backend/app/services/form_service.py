from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Form,
    FormAssignment,
    FormResponse as FormAnswer,
    FormSubmission,
    FormVersion,
    Product,
    Region,
    ScanEvent,
)
from app.schemas.forms import (
    FormAssignmentCreate,
    FormAssignmentUpdate,
    FormCreate,
    FormSchema,
    FormVersionUpdate,
)
from app.services.audit_service import record_audit_event


def _schema_audit_summary(schema_data: dict) -> dict:
    canonical = json.dumps(
        schema_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return {
        "field_count": len(schema_data.get("fields", [])),
        "schema_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _assignment_audit_values(assignment: FormAssignment) -> dict:
    return {
        "form_version_id": str(assignment.form_version_id),
        "scope_type": assignment.scope_type,
        "product_id": str(assignment.product_id) if assignment.product_id else None,
        "region_id": str(assignment.region_id) if assignment.region_id else None,
        "requirement": assignment.requirement,
        "is_active": assignment.is_active,
    }


def create_form(
    db: Session,
    data: FormCreate,
    *,
    admin_id: UUID | None = None,
) -> tuple[Form, FormVersion]:
    form = Form(name=data.name.strip(), description=data.description)
    db.add(form)
    db.flush()

    version = FormVersion(
        form_id=form.id,
        version_number=1,
        schema_data=data.schema_data.model_dump(mode="json"),
    )
    db.add(version)
    db.flush()
    record_audit_event(
        db,
        admin_id=admin_id,
        action="FORM_CREATED",
        entity_type="FORM",
        entity_id=form.id,
        new_values={
            "name": form.name,
            "version_number": version.version_number,
            **_schema_audit_summary(version.schema_data),
        },
    )
    db.commit()
    db.refresh(form)
    db.refresh(version)
    return form, version


def list_forms(db: Session) -> list[Form]:
    return list(db.scalars(select(Form).order_by(Form.created_at.desc(), Form.id)).all())


def list_form_versions(db: Session, form_id) -> list[FormVersion]:
    return list(db.scalars(
        select(FormVersion)
        .where(FormVersion.form_id == form_id)
        .order_by(FormVersion.version_number.desc())
    ).all())


def create_form_version(
    db: Session,
    form_id,
    schema: FormSchema,
    *,
    admin_id: UUID | None = None,
) -> FormVersion | None:
    form = db.execute(
        select(Form).where(Form.id == form_id).with_for_update()
    ).scalar_one_or_none()
    if form is None:
        return None
    latest_version = db.scalar(
        select(func.max(FormVersion.version_number)).where(FormVersion.form_id == form_id)
    ) or 0
    version = FormVersion(
        form_id=form_id,
        version_number=latest_version + 1,
        schema_data=schema.model_dump(mode="json"),
    )
    db.add(version)
    db.flush()
    record_audit_event(
        db,
        admin_id=admin_id,
        action="FORM_VERSION_CREATED",
        entity_type="FORM_VERSION",
        entity_id=version.id,
        new_values={
            "form_id": str(form_id),
            "version_number": version.version_number,
            **_schema_audit_summary(version.schema_data),
        },
    )
    db.commit()
    db.refresh(version)
    return version


def publish_form_version(
    db: Session,
    form_id,
    version_id,
    *,
    admin_id: UUID | None = None,
) -> FormVersion | None:
    version = db.execute(
        select(FormVersion)
        .where(FormVersion.form_id == form_id, FormVersion.id == version_id)
        .with_for_update()
    ).scalar_one_or_none()
    if version is None:
        return None
    if version.published_at is None:
        version.published_at = datetime.now(timezone.utc)
        record_audit_event(
            db,
            admin_id=admin_id,
            action="FORM_VERSION_PUBLISHED",
            entity_type="FORM_VERSION",
            entity_id=version.id,
            old_values={"published": False},
            new_values={
                "published": True,
                "form_id": str(form_id),
                "version_number": version.version_number,
            },
        )
        db.commit()
        db.refresh(version)
    return version


class FormVersionNotDraft(Exception):
    pass


def update_form_version(
    db: Session,
    form_id,
    version_id,
    data: FormVersionUpdate,
    *,
    admin_id: UUID | None = None,
) -> FormVersion:
    version = db.execute(
        select(FormVersion)
        .where(FormVersion.form_id == form_id, FormVersion.id == version_id)
        .with_for_update()
    ).scalar_one_or_none()
    if version is None:
        raise FormVersionNotFound()
    if version.published_at is not None:
        raise FormVersionNotDraft()
    old_schema = version.schema_data
    new_schema = data.schema_data.model_dump(mode="json")
    old_summary = _schema_audit_summary(old_schema)
    new_summary = _schema_audit_summary(new_schema)
    version.schema_data = new_schema
    if old_summary["schema_sha256"] != new_summary["schema_sha256"]:
        record_audit_event(
            db,
            admin_id=admin_id,
            action="FORM_VERSION_UPDATED",
            entity_type="FORM_VERSION",
            entity_id=version.id,
            old_values=old_summary,
            new_values=new_summary,
        )
    db.commit()
    db.refresh(version)
    return version


class FormVersionNotFound(Exception):
    pass


class FormAssignmentTargetMissing(Exception):
    pass


class FormVersionNotPublished(Exception):
    pass


def create_form_assignment(
    db: Session,
    data: FormAssignmentCreate,
    *,
    admin_id: UUID | None = None,
) -> FormAssignment:
    version = db.get(FormVersion, data.form_version_id)
    if version is None or version.published_at is None:
        raise FormVersionNotPublished()
    form = db.execute(
        select(Form).where(Form.id == version.form_id).with_for_update()
    ).scalar_one_or_none()
    if form is None or form.status != "ACTIVE":
        raise FormVersionNotPublished()

    if data.product_id is not None:
        product = db.get(Product, data.product_id)
        if product is None or product.status == "ARCHIVED":
            raise FormAssignmentTargetMissing()

    if data.region_id is not None:
        region = db.get(Region, data.region_id)
        if region is None or not region.is_active:
            raise FormAssignmentTargetMissing()

    existing_conditions = [
        FormVersion.form_id == form.id,
        FormAssignment.is_active.is_(True),
        FormAssignment.scope_type == data.scope_type,
    ]
    if data.scope_type == "PRODUCT":
        existing_conditions.append(FormAssignment.product_id == data.product_id)
    elif data.scope_type == "REGION":
        existing_conditions.append(FormAssignment.region_id == data.region_id)

    previous_assignments = db.scalars(
        select(FormAssignment)
        .join(FormVersion, FormVersion.id == FormAssignment.form_version_id)
        .where(*existing_conditions)
        .with_for_update()
    ).all()
    for previous in previous_assignments:
        previous.is_active = False

    assignment = FormAssignment(
        form_version_id=data.form_version_id,
        scope_type=data.scope_type,
        product_id=data.product_id,
        region_id=data.region_id,
        requirement=data.requirement,
        is_active=True,
    )
    db.add(assignment)
    db.flush()
    for previous in previous_assignments:
        record_audit_event(
            db,
            admin_id=admin_id,
            action="FORM_ASSIGNMENT_DEACTIVATED",
            entity_type="FORM_ASSIGNMENT",
            entity_id=previous.id,
            old_values={"is_active": True},
            new_values={
                "is_active": False,
                "replaced_by_assignment_id": str(assignment.id),
            },
        )
    record_audit_event(
        db,
        admin_id=admin_id,
        action="FORM_ASSIGNMENT_CREATED",
        entity_type="FORM_ASSIGNMENT",
        entity_id=assignment.id,
        new_values=_assignment_audit_values(assignment),
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def list_form_assignments(db: Session) -> list[FormAssignment]:
    return list(db.scalars(
        select(FormAssignment).order_by(FormAssignment.created_at.desc(), FormAssignment.id)
    ).all())


def update_form_assignment(
    db: Session,
    assignment_id,
    data: FormAssignmentUpdate,
    *,
    admin_id: UUID | None = None,
) -> FormAssignment | None:
    assignment = db.execute(
        select(FormAssignment)
        .where(FormAssignment.id == assignment_id)
        .with_for_update()
    ).scalar_one_or_none()
    if assignment is None:
        return None
    old_values = _assignment_audit_values(assignment)
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, name, value)
    new_values = _assignment_audit_values(assignment)
    if old_values != new_values:
        record_audit_event(
            db,
            admin_id=admin_id,
            action="FORM_ASSIGNMENT_UPDATED",
            entity_type="FORM_ASSIGNMENT",
            entity_id=assignment.id,
            old_values=old_values,
            new_values=new_values,
        )
    db.commit()
    db.refresh(assignment)
    return assignment


class ScanNotAllowedForForms(Exception):
    pass


class FormAssignmentUnavailable(Exception):
    pass


class InvalidFormAnswers(Exception):
    pass


class FormAlreadySubmitted(Exception):
    pass


def list_public_scan_forms(db: Session, scan_id):
    scan = db.get(ScanEvent, scan_id)
    if scan is None or scan.result_status != "ALLOWED" or scan.completed_at is None:
        raise ScanNotAllowedForForms()

    conditions = [FormAssignment.scope_type == "GLOBAL"]
    if scan.product_id:
        conditions.append(
            (FormAssignment.scope_type == "PRODUCT")
            & (FormAssignment.product_id == scan.product_id)
        )
    region_specificity = {}
    current_region_id = scan.region_id
    while current_region_id is not None and current_region_id not in region_specificity:
        region_specificity[current_region_id] = len(region_specificity)
        current_region = db.get(Region, current_region_id)
        current_region_id = current_region.parent_id if current_region is not None else None

    if region_specificity:
        conditions.append(
            (FormAssignment.scope_type == "REGION")
            & (FormAssignment.region_id.in_(region_specificity))
        )

    rows = db.execute(
        select(FormAssignment, FormVersion, Form)
        .join(FormVersion, FormVersion.id == FormAssignment.form_version_id)
        .join(Form, Form.id == FormVersion.form_id)
        .where(
            FormAssignment.is_active.is_(True),
            FormAssignment.requirement != "DISABLED",
            FormVersion.published_at.is_not(None),
            Form.status == "ACTIVE",
            or_(*conditions),
        )
    ).all()

    return select_effective_form_assignment(rows, region_specificity)


def select_effective_form_assignment(rows, region_specificity=None):
    """Keep distinct forms while resolving overlapping scopes for each form."""
    priority = {"REGION": 0, "PRODUCT": 1, "GLOBAL": 2}
    region_specificity = region_specificity or {}
    rows.sort(key=lambda row: (
        priority[row[0].scope_type],
        region_specificity.get(getattr(row[0], "region_id", None), 0)
        if row[0].scope_type == "REGION" else 0,
        -row[0].created_at.timestamp(),
    ))
    selected = {}
    for row in rows:
        selected.setdefault(row[2].id, row)
    return list(selected.values())


def _validated_form_answers(schema_data: dict, answers: dict) -> dict:
    try:
        schema = FormSchema.model_validate(schema_data)
    except Exception as error:
        raise InvalidFormAnswers() from error

    fields = {field.key: field for field in schema.fields}
    if any(key not in fields for key in answers):
        raise InvalidFormAnswers()

    normalized = {}
    for field in schema.fields:
        answer = answers.get(field.key)
        if answer is None or answer == "":
            if field.required:
                raise InvalidFormAnswers()
            continue

        if field.type == "CHECKBOX":
            if not isinstance(answer, bool):
                raise InvalidFormAnswers()
            normalized[field.key] = answer
        elif field.type == "SELECT":
            if not isinstance(answer, str) or answer not in field.options:
                raise InvalidFormAnswers()
            normalized[field.key] = answer
        else:
            if not isinstance(answer, str):
                raise InvalidFormAnswers()
            answer = answer.strip()
            if not answer or len(answer) > field.max_length:
                if field.required or answer:
                    raise InvalidFormAnswers()
                continue
            if field.type == "EMAIL" and ("@" not in answer or "." not in answer.rsplit("@", 1)[-1]):
                raise InvalidFormAnswers()
            if field.type == "PHONE":
                digits = re.sub(r"\D", "", answer)
                if not re.fullmatch(r"[+0-9().\-\s]+", answer) or not 7 <= len(digits) <= 15:
                    raise InvalidFormAnswers()
            normalized[field.key] = answer

    return normalized


def submit_public_form(db: Session, scan_id, assignment_id, answers: dict) -> FormSubmission:
    scan = db.execute(
        select(ScanEvent)
        .where(ScanEvent.id == scan_id)
        .with_for_update()
    ).scalar_one_or_none()
    if scan is None or scan.result_status != "ALLOWED" or scan.completed_at is None:
        raise ScanNotAllowedForForms()

    forms = list_public_scan_forms(db, scan_id)
    selected = next((row for row in forms if row[0].id == assignment_id), None)
    if selected is None:
        raise FormAssignmentUnavailable()
    assignment, version, _ = selected

    normalized = _validated_form_answers(version.schema_data, answers)
    existing = db.scalar(
        select(FormSubmission.id).where(
            FormSubmission.scan_event_id == scan_id,
            FormSubmission.form_assignment_id == assignment.id,
        )
    )
    if existing is not None:
        raise FormAlreadySubmitted()

    submission = FormSubmission(
        scan_event_id=scan_id,
        form_assignment_id=assignment.id,
    )
    db.add(submission)
    db.flush()
    db.add_all([
        FormAnswer(submission_id=submission.id, field_key=key, answer=value)
        for key, value in normalized.items()
    ])
    db.commit()
    db.refresh(submission)
    return submission


def list_form_submissions(
    db: Session,
    form_id,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    form_versions = select(FormVersion.id).where(FormVersion.form_id == form_id)
    assignments = select(FormAssignment.id).where(
        FormAssignment.form_version_id.in_(form_versions)
    )
    total = db.scalar(
        select(func.count(FormSubmission.id)).where(
            FormSubmission.form_assignment_id.in_(assignments)
        )
    ) or 0
    submissions = db.scalars(
        select(FormSubmission)
        .where(FormSubmission.form_assignment_id.in_(assignments))
        .order_by(FormSubmission.submitted_at.desc(), FormSubmission.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    answers_by_submission: dict[UUID, dict] = {
        submission.id: {} for submission in submissions
    }
    if submissions:
        for submission_id, field_key, answer in db.execute(
            select(FormAnswer.submission_id, FormAnswer.field_key, FormAnswer.answer)
            .where(FormAnswer.submission_id.in_(answers_by_submission))
            .order_by(FormAnswer.submission_id, FormAnswer.field_key)
        ):
            answers_by_submission[submission_id][field_key] = answer

    return {
        "items": [{
            "id": submission.id,
            "scan_event_id": submission.scan_event_id,
            "submitted_at": submission.submitted_at,
            "answers": answers_by_submission[submission.id],
        } for submission in submissions],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
