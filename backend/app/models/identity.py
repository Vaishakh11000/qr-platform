from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    name = Column(String(80), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    action = Column(String(100), nullable=False)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    ip_hash = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        Index("ix_audit_admin_time", "admin_id", text("created_at DESC")),
        Index(
            "ix_audit_entity",
            "entity_type",
            "entity_id",
            text("created_at DESC"),
        ),
    )
