from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, named_check


class LocationPolicy(Base):
    __tablename__ = "location_policies"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    name = Column(String(150), nullable=False)
    requirement = Column(String(20), nullable=False)
    method = Column(String(30), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("location_policies_requirement_check", "requirement IN ('MANDATORY', 'SKIPPABLE')"),
        named_check("location_policies_method_check", 
            "method IN ('GPS_REQUIRED', 'GPS_IP_FALLBACK', 'IP_ONLY')"
        ),
    )


class LocationPolicyAssignment(Base):
    __tablename__ = "location_policy_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.location_policies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope_type = Column(String(20), nullable=False)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.products.id", ondelete="RESTRICT"),
    )
    region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
    )
    priority = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("location_policy_assignments_check", 
            "(scope_type = 'GLOBAL' AND product_id IS NULL AND region_id IS NULL) "
            "OR (scope_type = 'PRODUCT' AND product_id IS NOT NULL AND region_id IS NULL) "
            "OR (scope_type = 'REGION' AND region_id IS NOT NULL AND product_id IS NULL)"
        ),
        named_check("location_policy_assignments_priority_check", "priority >= 0"),
        Index(
            "uq_location_global",
            "scope_type",
            unique=True,
            postgresql_where=text("scope_type = 'GLOBAL'"),
        ),
        Index(
            "uq_location_product",
            "product_id",
            unique=True,
            postgresql_where=text("scope_type = 'PRODUCT'"),
        ),
        Index(
            "uq_location_region",
            "region_id",
            unique=True,
            postgresql_where=text("scope_type = 'REGION'"),
        ),
        Index("ix_location_policy", "policy_id"),
    )
