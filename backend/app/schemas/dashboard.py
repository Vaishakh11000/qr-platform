from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductCounts(BaseModel):
    total: int
    active: int
    draft: int
    archived: int


class QRCodeCounts(BaseModel):
    total: int
    active: int
    inactive: int
    revoked: int
    allocated: int


class BatchCounts(BaseModel):
    total: int
    generated: int
    pending: int
    failed: int


class ScanCounts(BaseModel):
    total: int
    pending: int
    allowed: int
    blocked: int
    error: int


class DashboardOverview(BaseModel):
    products: ProductCounts
    qr_codes: QRCodeCounts
    batches: BatchCounts
    scans: ScanCounts


class ScanTrendItem(BaseModel):
    date: date
    total: int
    pending: int
    allowed: int
    blocked: int
    error: int


class LocationAnalytics(BaseModel):
    location_statuses: dict[str, int]
    classifications: dict[str, int]


class RecentActivityItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    created_at: datetime
