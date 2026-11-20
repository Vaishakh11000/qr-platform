from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, named_check


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))

    qr_code_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.qr_codes.id", ondelete="RESTRICT"),
        nullable=False,
    )

    allocation_id = Column(UUID(as_uuid=True))
    product_id = Column(UUID(as_uuid=True))
    region_id = Column(UUID(as_uuid=True))
    product_version_id = Column(UUID(as_uuid=True))

    location_policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.location_policies.id", ondelete="SET NULL"),
    )

    location_status = Column(
        String(30), nullable=False, server_default=text("'PENDING'")
    )
    result_status = Column(
        String(30), nullable=False, server_default=text("'PENDING'")
    )

    user_agent = Column(Text)
    ip_hash = Column(Text)
    scanned_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["allocation_id", "qr_code_id", "product_id", "region_id"],
            [
                "app.qr_allocations.id",
                "app.qr_allocations.qr_code_id",
                "app.qr_allocations.product_id",
                "app.qr_allocations.region_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["product_version_id", "product_id"],
            [
                "app.product_versions.id",
                "app.product_versions.product_id",
            ],
            ondelete="RESTRICT",
        ),
        named_check("scan_events_check", 
            "(allocation_id IS NULL AND product_id IS NULL AND region_id IS NULL) "
            "OR (allocation_id IS NOT NULL AND product_id IS NOT NULL AND region_id IS NOT NULL)"
        ),
        named_check("scan_events_location_status_check", 
            "location_status IN "
            "('PENDING', 'GPS', 'IP_DERIVED', 'SKIPPED', 'DENIED', "
            "'UNAVAILABLE', 'IP_LOOKUP_FAILED', 'UNCERTAIN')"
        ),
        named_check("scan_events_result_status_check", 
            "result_status IN ('PENDING', 'ALLOWED', 'BLOCKED', 'ERROR')"
        ),
        Index("ix_scan_qr_time", "qr_code_id", text("scanned_at DESC")),
        Index("ix_scan_product_time", "product_id", text("scanned_at DESC")),
        Index("ix_scan_region_time", "region_id", text("scanned_at DESC")),
        Index("ix_scan_time", text("scanned_at DESC")),
        Index(
            "ix_scan_result_time",
            "result_status",
            text("scanned_at DESC"),
        ),
        Index(
            "ix_scan_location_status",
            "location_status",
            text("scanned_at DESC"),
        ),
    )


class ScanLocation(Base):
    __tablename__ = "scan_locations"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))

    scan_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.scan_events.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    source = Column(String(20), nullable=False)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    accuracy_meters = Column(Numeric(12, 2))

    resolved_region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
    )

    confidence = Column(String(20))
    resolved_at = Column(DateTime(timezone=True), nullable=False,
                         server_default=func.now())

    __table_args__ = (
        named_check("scan_locations_source_check", "source IN ('GPS', 'IP')"),
        named_check("scan_locations_check", 
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)"
        ),
        named_check("scan_locations_accuracy_meters_check", 
            "accuracy_meters IS NULL OR accuracy_meters >= 0"
        ),
        named_check("scan_locations_confidence_check", 
            "confidence IS NULL OR "
            "confidence IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')"
        ),
        Index("ix_scan_location_region", "resolved_region_id"),
    )


class ScanClassification(Base):
    __tablename__ = "scan_classifications"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))

    scan_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.scan_events.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    assigned_region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    detected_region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
    )

    classification = Column(String(30), nullable=False)
    classified_at = Column(DateTime(timezone=True), nullable=False,
                           server_default=func.now())

    __table_args__ = (
        named_check("scan_classifications_classification_check", 
            "classification IN ('MATCH', 'MISMATCH', 'UNKNOWN', 'NOT_CHECKED')"
        ),
        Index(
            "ix_scan_classification",
            "classification",
            text("classified_at DESC"),
        ),
    )
