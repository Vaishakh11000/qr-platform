from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScanStartRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)

    @field_validator("token")
    @classmethod
    def clean_token(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("QR token cannot be empty.")
        return value


class ScanStartResponse(BaseModel):
    scan_id: UUID
    location_requested: bool
    location_requirement: Literal["MANDATORY", "SKIPPABLE"] | None
    location_method: Literal[
        "GPS_REQUIRED",
        "GPS_IP_FALLBACK",
        "IP_ONLY",
    ] | None


class ScanLocationSubmission(BaseModel):
    location_status: Literal[
        "GPS",
        "SKIPPED",
        "DENIED",
        "UNAVAILABLE",
    ]

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=100000)

    @model_validator(mode="after")
    def validate_location(self):
        if self.location_status == "GPS":
            if self.latitude is None or self.longitude is None:
                raise ValueError(
                    "GPS coordinates are required for GPS location status."
                )
        elif (
            self.latitude is not None
            or self.longitude is not None
            or self.accuracy_meters is not None
        ):
            raise ValueError(
                "Coordinates are only accepted with GPS location status."
            )

        return self


class ScanProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_id: UUID
    version_number: int
    sku: str
    name: str
    content_snapshot: dict[str, Any]


class ScanCompletionResponse(BaseModel):
    scan_id: UUID
    result_status: Literal["ALLOWED", "BLOCKED"]
    location_status: str
    message: str
    product: ScanProductResponse | None = None
