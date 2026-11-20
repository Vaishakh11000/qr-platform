from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    category_id: UUID | None = None
    short_description: str | None = None

    @field_validator("sku", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: UUID | None = None
    short_description: str | None = None

    @field_validator("sku", "name")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This field cannot be null.")

        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    name: str
    category_id: UUID | None
    short_description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
