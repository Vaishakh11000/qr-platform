from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import column, literal_column
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy import func as sql_func

from .base import Base, named_check


class QRBatch(Base):
    __tablename__ = "qr_batches"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    batch_code = Column(String(100), nullable=False, unique=True)
    requested_product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.products.id", ondelete="RESTRICT"),
    )
    requested_region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
    )
    quantity = Column(Integer, nullable=False)
    generation_status = Column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )
    retired_at = Column(DateTime(timezone=True))
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        named_check("qr_batches_quantity_check", "quantity > 0"),
        named_check("qr_batches_generation_status_check", 
            "generation_status IN ('PENDING', 'GENERATED', 'FAILED')"
        ),
    )


class QRCode(Base):
    __tablename__ = "qr_codes"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.qr_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token = Column(String(128), nullable=False, unique=True)
    status = Column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    deactivated_at = Column(DateTime(timezone=True))

    __table_args__ = (
        named_check("qr_codes_status_check", "status IN ('ACTIVE', 'INACTIVE', 'REVOKED')"),
        named_check("qr_codes_check", 
            "(status = 'ACTIVE' AND deactivated_at IS NULL) OR "
            "(status <> 'ACTIVE' AND deactivated_at IS NOT NULL)"
        ),
        Index("ix_qr_batch", "batch_id"),
        Index("ix_qr_status", "status"),
    )


class QRAllocation(Base):
    __tablename__ = "qr_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    qr_code_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.qr_codes.id", ondelete="RESTRICT"),
        nullable=False,
    )
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
    assigned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    assigned_at = Column(DateTime(timezone=True), nullable=False,
                         server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    reason = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            "id", "qr_code_id", "product_id", "region_id"
        ),
        named_check("qr_allocations_check", "ended_at IS NULL OR ended_at > assigned_at"),
        ExcludeConstraint(
	    ("qr_code_id", "="),
	    (
	        sql_func.tstzrange(
	            column("assigned_at"),
	            column("ended_at"),
	            literal_column("'[)'"),
	        ),
	        "&&",
	    ),
	    using="gist",
	    name="qr_allocations_qr_code_id_tstzrange_excl",
	),
        Index(
            "uq_qr_active_allocation",
            "qr_code_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_allocation_product",
            "product_id",
            text("assigned_at DESC"),
        ),
        Index(
            "ix_allocation_region",
            "region_id",
            text("assigned_at DESC"),
        ),
        Index(
            "ix_allocation_history",
            "qr_code_id",
            text("assigned_at DESC"),
        ),
    )
