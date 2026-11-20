from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    region_code: str = Field(min_length=1, max_length=50)
    region_type: str = Field(min_length=1, max_length=50)
    parent_id: UUID | None = None

    @field_validator("name", "region_code", "region_type")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value


class RegionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    region_code: str | None = Field(default=None, min_length=1, max_length=50)
    region_type: str | None = Field(default=None, min_length=1, max_length=50)
    parent_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("name", "region_code", "region_type")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This field cannot be null.")

        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty.")

        return value


class RegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    region_code: str
    region_type: str
    parent_id: UUID | None
    is_active: bool
    created_at: datetime


class RegionBoundaryGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class RegionBoundaryUpdate(BaseModel):
    geometry: RegionBoundaryGeometry


class RegionBoundaryResponse(BaseModel):
    region_id: UUID
    geometry: dict[str, Any] | None


class RegionBoundaryDeleteResponse(BaseModel):
    deleted: bool
