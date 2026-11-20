from datetime import datetime
from uuid import UUID

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class PlatformSettingsResponse(BaseModel):
    public_base_url: str


class PlatformSettingsUpdate(BaseModel):
    public_base_url: str = Field(min_length=8, max_length=2048)

    @field_validator("public_base_url")
    @classmethod
    def validate_public_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Enter a valid public HTTP or HTTPS base URL.")
        return value
