from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    CheckConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base, named_check


class AnalyticsDaily(Base):
    __tablename__ = "analytics_daily"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    report_date = Column(Date, nullable=False)

    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    total_scans = Column(BigInteger, nullable=False,
                         server_default=text("0"))
    gps_scans = Column(BigInteger, nullable=False,
                       server_default=text("0"))
    ip_scans = Column(BigInteger, nullable=False,
                      server_default=text("0"))
    skipped_scans = Column(BigInteger, nullable=False,
                           server_default=text("0"))
    mismatch_scans = Column(BigInteger, nullable=False,
                            server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("report_date", "product_id", "region_id"),
        named_check("analytics_daily_check", 
            "total_scans >= 0 AND "
            "gps_scans >= 0 AND "
            "ip_scans >= 0 AND "
            "skipped_scans >= 0 AND "
            "mismatch_scans >= 0"
        ),
        Index("ix_analytics_date", text("report_date DESC")),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    setting_key = Column(String(100), nullable=False, unique=True)
    setting_value = Column(JSONB, nullable=False)

    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )

    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
