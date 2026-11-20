from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base, named_check


class Form(Base):
    __tablename__ = "forms"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    name = Column(String(150), nullable=False)
    description = Column(Text)
    status = Column(String(20), nullable=False,
                    server_default=text("'ACTIVE'"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("forms_status_check", "status IN ('ACTIVE', 'INACTIVE')"),
    )


class FormVersion(Base):
    __tablename__ = "form_versions"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    form_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.forms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number = Column(Integer, nullable=False)

    # "schema" is a reserved SQLAlchemy metadata attribute,
    # so use a different Python attribute for the database column.
    schema_data = Column("schema", JSONB, nullable=False)

    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        UniqueConstraint("form_id", "version_number"),
        UniqueConstraint("id", "form_id"),
        named_check("form_versions_version_number_check", "version_number > 0"),
    )


class FormAssignment(Base):
    __tablename__ = "form_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    form_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.form_versions.id", ondelete="RESTRICT"),
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

    requirement = Column(
        String(20), nullable=False, server_default=text("'OPTIONAL'")
    )
    is_active = Column(Boolean, nullable=False,
                        server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("form_assignments_check", 
            "(scope_type = 'GLOBAL' AND product_id IS NULL AND region_id IS NULL) "
            "OR (scope_type = 'PRODUCT' AND product_id IS NOT NULL AND region_id IS NULL) "
            "OR (scope_type = 'REGION' AND region_id IS NOT NULL AND product_id IS NULL)"
        ),
        named_check("form_assignments_requirement_check", 
            "requirement IN ('MANDATORY', 'OPTIONAL', 'DISABLED')"
        ),
        Index(
            "ix_form_assignment_product",
            "product_id",
            postgresql_where=text("scope_type = 'PRODUCT'"),
        ),
        Index(
            "ix_form_assignment_region",
            "region_id",
            postgresql_where=text("scope_type = 'REGION'"),
        ),
    )


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    scan_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.scan_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    form_assignment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.form_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submitted_at = Column(DateTime(timezone=True), nullable=False,
                          server_default=func.now())

    __table_args__ = (
        Index("ix_form_submission_scan", "scan_event_id"),
    )


class FormResponse(Base):
    __tablename__ = "form_responses"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.form_submissions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_key = Column(String(100), nullable=False)
    answer = Column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("submission_id", "field_key"),
    )
