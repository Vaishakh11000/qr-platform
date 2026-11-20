from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FormField(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    label: str = Field(min_length=1, max_length=200)
    type: Literal["TEXT", "EMAIL", "PHONE", "TEXTAREA", "SELECT", "CHECKBOX"]
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)
    max_length: int = Field(default=500, ge=1, le=5000)

    @model_validator(mode="after")
    def validate_options(self):
        if self.type == "SELECT" and not self.options:
            raise ValueError("Select fields need at least one option.")
        if self.type != "SELECT" and self.options:
            raise ValueError("Only select fields can have options.")
        if any(not option.strip() or len(option) > 200 for option in self.options):
            raise ValueError("Options must contain 1 to 200 characters.")
        return self


class FormSchema(BaseModel):
    fields: list[FormField] = Field(min_length=1, max_length=30)

    @field_validator("fields")
    @classmethod
    def validate_unique_keys(cls, fields: list[FormField]):
        keys = [field.key for field in fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Form field keys must be unique.")
        return fields


class FormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    schema_data: FormSchema = Field(alias="schema")


class FormResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime


class FormVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_id: UUID
    version_number: int
    schema_data: dict[str, Any] = Field(serialization_alias="schema")
    published_at: datetime | None
    created_at: datetime


class FormVersionUpdate(BaseModel):
    schema_data: FormSchema = Field(alias="schema")


class FormAssignmentCreate(BaseModel):
    form_version_id: UUID
    scope_type: Literal["GLOBAL", "PRODUCT", "REGION"]
    product_id: UUID | None = None
    region_id: UUID | None = None
    requirement: Literal["MANDATORY", "OPTIONAL", "DISABLED"] = "OPTIONAL"

    @model_validator(mode="after")
    def validate_scope(self):
        valid = (
            self.scope_type == "GLOBAL" and self.product_id is None and self.region_id is None
        ) or (
            self.scope_type == "PRODUCT" and self.product_id is not None and self.region_id is None
        ) or (
            self.scope_type == "REGION" and self.region_id is not None and self.product_id is None
        )
        if not valid:
            raise ValueError("Choose exactly the target required by the assignment scope.")
        return self


class FormAssignmentUpdate(BaseModel):
    is_active: bool | None = None
    requirement: Literal["MANDATORY", "OPTIONAL", "DISABLED"] | None = None

    @model_validator(mode="after")
    def require_a_change(self):
        if self.is_active is None and self.requirement is None:
            raise ValueError("Provide an assignment status or requirement to update.")
        return self


class FormAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    form_version_id: UUID
    scope_type: str
    product_id: UUID | None
    region_id: UUID | None
    requirement: str
    is_active: bool
    created_at: datetime


class FormSubmissionCreate(BaseModel):
    answers: dict[str, Any] = Field(max_length=30)


class PublicFormResponse(BaseModel):
    id: UUID
    form_id: UUID
    name: str
    description: str | None
    version_number: int
    requirement: Literal["MANDATORY", "OPTIONAL"]
    schema_data: dict[str, Any] = Field(serialization_alias="schema")


class FormSubmissionResponse(BaseModel):
    id: UUID
    submitted_at: datetime


class FormSubmissionAdminResponse(BaseModel):
    id: UUID
    scan_event_id: UUID
    submitted_at: datetime
    answers: dict[str, Any]


class FormSubmissionAdminPage(BaseModel):
    items: list[FormSubmissionAdminResponse]
    total: int
    offset: int
    limit: int
