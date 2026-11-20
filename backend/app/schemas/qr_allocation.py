from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class QRAllocationCreate(BaseModel):
    qr_code_ids: list[UUID] = Field(
        min_length=1,
        max_length=5000,
    )
    product_id: UUID
    region_id: UUID
    reason: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("qr_code_ids")
    @classmethod
    def validate_unique_qr_codes(
        cls,
        value: list[UUID],
    ) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate QR code IDs are not allowed.")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class QRAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    qr_code_id: UUID
    product_id: UUID
    region_id: UUID
    assigned_by: UUID | None
    assigned_at: datetime
    ended_at: datetime | None
    reason: str | None


class QRAllocationReassign(BaseModel):
    product_id: UUID
    region_id: UUID
    reason: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class QRBatchAllocationRequest(BaseModel):
    product_id: UUID
    region_id: UUID
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class QRBatchAllocationResponse(BaseModel):
    batch_id: UUID
    batch_code: str
    active_code_count: int
    allocated_count: int
    reassigned_count: int
    unchanged_count: int
