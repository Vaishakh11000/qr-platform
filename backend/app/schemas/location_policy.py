from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


PolicyRequirement = Literal["MANDATORY", "SKIPPABLE"]
PolicyMethod = Literal["GPS_REQUIRED", "GPS_IP_FALLBACK", "IP_ONLY"]
AssignmentScope = Literal["GLOBAL", "PRODUCT", "REGION"]


class LocationPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    requirement: PolicyRequirement
    method: PolicyMethod

    @model_validator(mode="after")
    def validate_policy(self):
        self.name = self.name.strip()

        if not self.name:
            raise ValueError("Policy name cannot be empty.")

        return self


class LocationPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    requirement: PolicyRequirement | None = None
    method: PolicyMethod | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        if self.name is not None:
            self.name = self.name.strip()

            if not self.name:
                raise ValueError("Policy name cannot be empty.")

        return self


class LocationPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    requirement: str
    method: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class LocationPolicyAssignmentCreate(BaseModel):
    policy_id: UUID
    scope_type: AssignmentScope
    product_id: UUID | None = None
    region_id: UUID | None = None
    priority: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope_type == "GLOBAL":
            if self.product_id is not None or self.region_id is not None:
                raise ValueError(
                    "GLOBAL assignments cannot specify a product or region."
                )

        elif self.scope_type == "PRODUCT":
            if self.product_id is None or self.region_id is not None:
                raise ValueError(
                    "PRODUCT assignments require product_id only."
                )

        elif self.scope_type == "REGION":
            if self.region_id is None or self.product_id is not None:
                raise ValueError(
                    "REGION assignments require region_id only."
                )

        return self


class LocationPolicyAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_id: UUID
    scope_type: str
    product_id: UUID | None
    region_id: UUID | None
    priority: int
    created_at: datetime
