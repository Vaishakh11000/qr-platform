from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QRBatchCreate(BaseModel):
    quantity: int = Field(ge=1, le=5000)
    batch_code: str | None = Field(default=None, min_length=1, max_length=100)
    requested_product_id: UUID | None = None
    requested_region_id: UUID | None = None

    @field_validator("batch_code")
    @classmethod
    def validate_batch_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Batch code cannot be empty.")

        return value


class QRBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_code: str
    requested_product_id: UUID | None
    requested_region_id: UUID | None
    quantity: int
    generation_status: str
    created_by: UUID | None
    created_at: datetime
    completed_at: datetime | None
    retired_at: datetime | None = None
    current_product_id: UUID | None = None
    current_region_id: UUID | None = None
    allocation_status: Literal[
        "UNALLOCATED", "ALLOCATED", "MIXED", "NO_ACTIVE_CODES"
    ] = "UNALLOCATED"
    active_code_count: int = 0
    allocated_code_count: int = 0


class QRBatchRetireResponse(BaseModel):
    batch_id: UUID
    batch_code: str
    revoked_count: int
    retired_at: datetime


class QRCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    token: str
    status: str
    created_at: datetime
    scan_url: str
