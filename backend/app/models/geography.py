from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from .base import Base, named_check


class Region(Base):
    __tablename__ = "regions"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    name = Column(String(150), nullable=False)
    region_code = Column(String(50), nullable=False, unique=True)
    region_type = Column(String(50), nullable=False)
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
    )
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("regions_check", "parent_id IS NULL OR parent_id <> id"),
        Index("ix_regions_parent", "parent_id"),
        Index("ix_regions_type", "region_type"),
    )


class RegionBoundary(Base):
    __tablename__ = "region_boundaries"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    region_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.regions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    boundary = Column(
        Geometry(
            geometry_type="MULTIPOLYGON",
            srid=4326,
            spatial_index=False,
        ),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        Index(
            "ix_region_boundary_geom",
            "boundary",
            postgresql_using="gist",
        ),
    )
