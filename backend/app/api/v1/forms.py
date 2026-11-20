from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser, Form
from app.schemas.forms import (
    FormAssignmentCreate,
    FormAssignmentResponse,
    FormCreate,
    FormResponse,
    FormVersionResponse,
    FormSubmissionAdminResponse,
    FormSubmissionAdminPage,
    FormVersionUpdate,
    FormAssignmentUpdate,
)
from app.services.form_service import (
    create_form,
    list_form_versions,
    list_forms,
    publish_form_version,
    create_form_assignment,
    list_form_assignments,
    FormAssignmentTargetMissing,
    FormVersionNotPublished,
    list_form_submissions,
    update_form_version,
    update_form_assignment,
    FormVersionNotDraft,
    FormVersionNotFound,
    create_form_version,
)
router = APIRouter(
    prefix="/forms",
    tags=["Forms"],
    dependencies=[Depends(require_super_admin)],
)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_form_endpoint(
    data: FormCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    form, version = create_form(db, data, admin_id=actor.id)
    return {
        "form": FormResponse.model_validate(form),
        "version": FormVersionResponse.model_validate(version),
    }


@router.get("", response_model=list[FormResponse])
def list_forms_endpoint(db: Session = Depends(get_db)):
    return list_forms(db)


@router.get("/{form_id}/versions", response_model=list[FormVersionResponse])
def list_form_versions_endpoint(
    form_id: UUID,
    db: Session = Depends(get_db),
):
    versions = list_form_versions(db, form_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Form not found.")
    return versions


@router.post("/{form_id}/versions", response_model=FormVersionResponse, status_code=status.HTTP_201_CREATED)
def create_form_version_endpoint(
    form_id: UUID,
    data: FormVersionUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    version = create_form_version(
        db,
        form_id,
        data.schema_data,
        admin_id=actor.id,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    return version


@router.post(
    "/{form_id}/versions/{version_id}/publish",
    response_model=FormVersionResponse,
)
def publish_form_version_endpoint(
    form_id: UUID,
    version_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    version = publish_form_version(
        db,
        form_id,
        version_id,
        admin_id=actor.id,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Form version not found.")
    return version


@router.patch(
    "/{form_id}/versions/{version_id}",
    response_model=FormVersionResponse,
)
def update_form_version_endpoint(
    form_id: UUID,
    version_id: UUID,
    data: FormVersionUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_form_version(
            db,
            form_id,
            version_id,
            data,
            admin_id=actor.id,
        )
    except FormVersionNotFound:
        raise HTTPException(status_code=404, detail="Form version not found.")
    except FormVersionNotDraft:
        raise HTTPException(status_code=409, detail="Published form versions cannot be edited.")


@router.post(
    "/assignments",
    status_code=status.HTTP_201_CREATED,
    response_model=FormAssignmentResponse,
)
def create_form_assignment_endpoint(
    data: FormAssignmentCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return create_form_assignment(db, data, admin_id=actor.id)
    except FormVersionNotPublished:
        raise HTTPException(status_code=409, detail="Publish the form version before assigning it.")
    except FormAssignmentTargetMissing:
        raise HTTPException(status_code=404, detail="The selected product or active region was not found.")


@router.get("/assignments", response_model=list[FormAssignmentResponse])
def list_form_assignments_endpoint(db: Session = Depends(get_db)):
    return list_form_assignments(db)


@router.patch("/assignments/{assignment_id}", response_model=FormAssignmentResponse)
def update_form_assignment_endpoint(
    assignment_id: UUID,
    data: FormAssignmentUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    assignment = update_form_assignment(
        db,
        assignment_id,
        data,
        admin_id=actor.id,
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Form assignment not found.")
    return assignment


@router.get("/{form_id}/submissions", response_model=FormSubmissionAdminPage)
def list_form_submissions_endpoint(
    form_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if db.get(Form, form_id) is None:
        raise HTTPException(status_code=404, detail="Form not found.")
    return list_form_submissions(db, form_id, offset=offset, limit=limit)
