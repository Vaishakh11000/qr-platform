from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.forms import (
    FormSubmissionCreate,
    FormSubmissionResponse,
    PublicFormResponse,
)
from app.services.form_service import (
    FormAlreadySubmitted,
    FormAssignmentUnavailable,
    InvalidFormAnswers,
    ScanNotAllowedForForms,
    list_public_scan_forms,
    submit_public_form,
)


router = APIRouter(
    prefix="/public/scans/{scan_id}/forms",
    tags=["Public Forms"],
)


@router.get("", response_model=list[PublicFormResponse])
def get_public_scan_forms(
    scan_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        forms = list_public_scan_forms(db, scan_id)
    except ScanNotAllowedForForms:
        raise HTTPException(status_code=404, detail="Forms not found.")

    return [
        PublicFormResponse(
            id=assignment.id,
            form_id=form.id,
            name=form.name,
            description=form.description,
            version_number=version.version_number,
            requirement=assignment.requirement,
            schema_data=version.schema_data,
        )
        for assignment, version, form in forms
    ]


@router.post("/{assignment_id}", response_model=FormSubmissionResponse, status_code=201)
def submit_public_scan_form(
    scan_id: UUID,
    assignment_id: UUID,
    data: FormSubmissionCreate,
    db: Session = Depends(get_db),
):
    try:
        return submit_public_form(db, scan_id, assignment_id, data.answers)
    except ScanNotAllowedForForms:
        raise HTTPException(status_code=404, detail="Form not found.")
    except FormAssignmentUnavailable:
        raise HTTPException(status_code=404, detail="Form not found.")
    except InvalidFormAnswers:
        raise HTTPException(status_code=422, detail="Check the form answers and try again.")
    except FormAlreadySubmitted:
        raise HTTPException(status_code=409, detail="This form was already submitted for this scan.")
