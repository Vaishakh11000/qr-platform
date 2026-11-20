from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ProductVersionCreate(BaseModel):
    content_snapshot: dict[str, Any]


class ProductVersionUpdate(BaseModel):
    content_snapshot: dict[str, Any] | None = None

    @field_validator("content_snapshot")
    @classmethod
    def validate_content_snapshot(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if value is None:
            raise ValueError("Content snapshot cannot be null.")

        return value


class ProductVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    version_number: int
    content_snapshot: dict[str, Any]
    status: str
    created_at: datetime
    published_at: datetime | None
