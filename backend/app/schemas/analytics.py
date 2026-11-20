from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.schemas.dashboard import LocationAnalytics, ScanCounts, ScanTrendItem


class ProductScanBreakdown(BaseModel):
    product_id: UUID | None
    name: str
    sku: str | None
    scans: int


class RegionScanBreakdown(BaseModel):
    region_id: UUID | None
    name: str
    region_code: str | None
    scans: int


class QRScanBreakdown(BaseModel):
    qr_code_id: UUID
    batch_code: str
    token_suffix: str
    scans: int


class ScanAnalyticsResponse(BaseModel):
    from_date: date
    to_date: date
    summary: ScanCounts
    location_analytics: LocationAnalytics
    daily: list[ScanTrendItem]
    products: list[ProductScanBreakdown]
    regions: list[RegionScanBreakdown]
    qr_codes: list[QRScanBreakdown]
