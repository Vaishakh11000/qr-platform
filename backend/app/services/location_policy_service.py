from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    LocationPolicy,
    LocationPolicyAssignment,
    Product,
    Region,
)
from app.services.audit_service import record_audit_event


def _policy_snapshot(policy: LocationPolicy) -> dict:
    return {
        "name": policy.name,
        "requirement": policy.requirement,
        "method": policy.method,
        "is_active": policy.is_active,
    }


def _assignment_snapshot(
    assignment: LocationPolicyAssignment,
) -> dict:
    return {
        "policy_id": str(assignment.policy_id),
        "scope_type": assignment.scope_type,
        "product_id": (
            str(assignment.product_id)
            if assignment.product_id else None
        ),
        "region_id": (
            str(assignment.region_id)
            if assignment.region_id else None
        ),
        "priority": assignment.priority,
    }


# Exceptions

class LocationPolicyError(Exception):
    pass


class LocationPolicyNotFound(LocationPolicyError):
    pass


class LocationPolicyInactive(LocationPolicyError):
    pass


class LocationPolicyActive(LocationPolicyError):
    pass


class InvalidLocationPolicy(LocationPolicyError):
    pass


class LocationPolicyAssignmentNotFound(LocationPolicyError):
    pass


class AssignmentAlreadyExists(LocationPolicyError):
    pass


class AssignmentTargetNotFound(LocationPolicyError):
    pass


class AssignmentConflict(LocationPolicyError):
    pass


# Policy operations

def create_policy(db: Session, data, admin_id: UUID) -> LocationPolicy:
    policy = LocationPolicy(
        name=data.name,
        requirement=data.requirement,
        method=data.method,
        is_active=True,
        created_by=admin_id,
    )

    db.add(policy)
    db.flush()

    record_audit_event(
        db,
        admin_id=admin_id,
        action="LOCATION_POLICY_CREATED",
        entity_type="LOCATION_POLICY",
        entity_id=policy.id,
        new_values=_policy_snapshot(policy),
    )

    db.commit()
    db.refresh(policy)

    return policy


def get_policy(db: Session, policy_id: UUID) -> LocationPolicy:
    policy = db.get(LocationPolicy, policy_id)

    if policy is None:
        raise LocationPolicyNotFound()

    return policy


def list_policies(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
) -> list[LocationPolicy]:

    query = select(LocationPolicy)

    if is_active is not None:
        query = query.where(LocationPolicy.is_active.is_(is_active))

    query = query.order_by(
        LocationPolicy.created_at.desc(),
        LocationPolicy.id.desc(),
    ).offset(offset).limit(limit)

    return list(db.scalars(query).all())


def update_policy(
    db: Session,
    policy_id: UUID,
    data,
    admin_id: UUID,
) -> LocationPolicy:

    policy = get_policy(db, policy_id)
    old_values = _policy_snapshot(policy)
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise InvalidLocationPolicy()

    if any(value is None for value in changes.values()):
        raise InvalidLocationPolicy()

    for field, value in changes.items():
        setattr(policy, field, value)

    policy.updated_at = datetime.now(timezone.utc)

    record_audit_event(
        db,
        admin_id=admin_id,
        action="LOCATION_POLICY_UPDATED",
        entity_type="LOCATION_POLICY",
        entity_id=policy.id,
        old_values=old_values,
        new_values=_policy_snapshot(policy),
    )

    db.commit()
    db.refresh(policy)

    return policy


def deactivate_policy(
    db: Session,
    policy_id: UUID,
    admin_id: UUID,
) -> LocationPolicy:

    policy = get_policy(db, policy_id)

    if not policy.is_active:
        return policy

    old_values = _policy_snapshot(policy)

    policy.is_active = False
    policy.updated_at = datetime.now(timezone.utc)

    record_audit_event(
        db,
        admin_id=admin_id,
        action="LOCATION_POLICY_DEACTIVATED",
        entity_type="LOCATION_POLICY",
        entity_id=policy.id,
        old_values=old_values,
        new_values=_policy_snapshot(policy),
    )

    db.commit()
    db.refresh(policy)

    return policy


def permanently_delete_policy(
    db: Session,
    policy_id: UUID,
    admin_id: UUID,
) -> None:
    policy = get_policy(db, policy_id)
    if policy.is_active:
        raise LocationPolicyActive()

    policy_id_for_audit = policy.id
    old_values = _policy_snapshot(policy)
    assignment_rows = db.scalars(
        select(LocationPolicyAssignment).where(
            LocationPolicyAssignment.policy_id == policy_id
        )
    ).all()
    old_values["assignments"] = [
        _assignment_snapshot(assignment) for assignment in assignment_rows
    ]

    db.execute(
        delete(LocationPolicyAssignment).where(
            LocationPolicyAssignment.policy_id == policy_id
        )
    )
    db.delete(policy)
    record_audit_event(
        db,
        admin_id=admin_id,
        action="LOCATION_POLICY_DELETED",
        entity_type="LOCATION_POLICY",
        entity_id=policy_id_for_audit,
        old_values=old_values,
    )
    db.commit()


# Assignment validation

def _validate_assignment_target(db: Session, data):
    if data.scope_type == "GLOBAL":
        if data.product_id is not None or data.region_id is not None:
            raise InvalidLocationPolicy()

    elif data.scope_type == "PRODUCT":
        if data.product_id is None or data.region_id is not None:
            raise InvalidLocationPolicy()

        product = db.get(Product, data.product_id)

        if product is None or product.status == "ARCHIVED":
            raise AssignmentTargetNotFound()

    elif data.scope_type == "REGION":
        if data.region_id is None or data.product_id is not None:
            raise InvalidLocationPolicy()

        region = db.get(Region, data.region_id)

        if region is None or not region.is_active:
            raise AssignmentTargetNotFound()

    else:
        raise InvalidLocationPolicy()


def _get_existing_assignment(
    db: Session,
    data,
    *,
    exclude_id: UUID | None = None,
):
    query = select(LocationPolicyAssignment).where(
        LocationPolicyAssignment.scope_type == data.scope_type
    )

    if data.scope_type == "PRODUCT":
        query = query.where(
            LocationPolicyAssignment.product_id == data.product_id
        )

    elif data.scope_type == "REGION":
        query = query.where(
            LocationPolicyAssignment.region_id == data.region_id
        )

    if exclude_id is not None:
        query = query.where(
            LocationPolicyAssignment.id != exclude_id
        )

    return db.scalar(query)


def _validate_assignment_policy(db: Session, policy_id: UUID):
    policy = db.get(LocationPolicy, policy_id)

    if policy is None:
        raise LocationPolicyNotFound()

    if not policy.is_active:
        raise LocationPolicyInactive()

    return policy


# Assignment operations

def create_assignment(
    db: Session,
    data,
    admin_id: UUID,
) -> LocationPolicyAssignment:
    _validate_assignment_policy(db, data.policy_id)
    _validate_assignment_target(db, data)

    existing = _get_existing_assignment(db, data)

    if existing is not None:
        raise AssignmentAlreadyExists()

    assignment = LocationPolicyAssignment(
        policy_id=data.policy_id,
        scope_type=data.scope_type,
        product_id=data.product_id,
        region_id=data.region_id,
        priority=data.priority,
    )

    try:
        db.add(assignment)
        db.flush()

        record_audit_event(
            db,
            admin_id=admin_id,
            action="LOCATION_POLICY_ASSIGNMENT_CREATED",
            entity_type="LOCATION_POLICY_ASSIGNMENT",
            entity_id=assignment.id,
            new_values=_assignment_snapshot(assignment),
        )

        db.commit()
        db.refresh(assignment)

    except IntegrityError as exc:
        db.rollback()
        raise AssignmentConflict() from exc

    return assignment


def get_assignment(
    db: Session,
    assignment_id: UUID,
) -> LocationPolicyAssignment:

    assignment = db.get(LocationPolicyAssignment, assignment_id)

    if assignment is None:
        raise LocationPolicyAssignmentNotFound()

    return assignment


def list_assignments(
    db: Session,
    *,
    policy_id: UUID | None = None,
    scope_type: str | None = None,
    product_id: UUID | None = None,
    region_id: UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[LocationPolicyAssignment]:

    query = select(LocationPolicyAssignment)

    if policy_id is not None:
        query = query.where(
            LocationPolicyAssignment.policy_id == policy_id
        )

    if scope_type is not None:
        query = query.where(
            LocationPolicyAssignment.scope_type == scope_type
        )

    if product_id is not None:
        query = query.where(
            LocationPolicyAssignment.product_id == product_id
        )

    if region_id is not None:
        query = query.where(
            LocationPolicyAssignment.region_id == region_id
        )

    query = query.order_by(
        LocationPolicyAssignment.created_at.desc(),
        LocationPolicyAssignment.id.desc(),
    ).offset(offset).limit(limit)

    return list(db.scalars(query).all())


def replace_assignment(
    db: Session,
    assignment_id: UUID,
    data,
    admin_id: UUID,
) -> LocationPolicyAssignment:

    assignment = get_assignment(db, assignment_id)
    old_values = _assignment_snapshot(assignment)

    _validate_assignment_policy(db, data.policy_id)
    _validate_assignment_target(db, data)

    existing = _get_existing_assignment(
        db,
        data,
        exclude_id=assignment_id,
    )

    if existing is not None:
        raise AssignmentAlreadyExists()

    assignment.policy_id = data.policy_id
    assignment.scope_type = data.scope_type
    assignment.product_id = data.product_id
    assignment.region_id = data.region_id
    assignment.priority = data.priority

    try:
        db.flush()

        record_audit_event(
            db,
            admin_id=admin_id,
            action="LOCATION_POLICY_ASSIGNMENT_UPDATED",
            entity_type="LOCATION_POLICY_ASSIGNMENT",
            entity_id=assignment.id,
            old_values=old_values,
            new_values=_assignment_snapshot(assignment),
        )

        db.commit()
        db.refresh(assignment)

    except IntegrityError as exc:
        db.rollback()
        raise AssignmentConflict() from exc

    return assignment


def delete_assignment(
    db: Session,
    assignment_id: UUID,
    admin_id: UUID,
) -> None:

    assignment = get_assignment(db, assignment_id)
    old_values = _assignment_snapshot(assignment)

    db.delete(assignment)

    record_audit_event(
        db,
        admin_id=admin_id,
        action="LOCATION_POLICY_ASSIGNMENT_DELETED",
        entity_type="LOCATION_POLICY_ASSIGNMENT",
        entity_id=assignment_id,
        old_values=old_values,
    )

    db.commit()
