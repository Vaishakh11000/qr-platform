from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    name = Column(String(150), nullable=False)
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.product_categories.id", ondelete="RESTRICT"),
    )
    description = Column(Text)
    is_active = Column(Boolean,
                       nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("product_categories_check", "parent_id IS NULL OR parent_id <> id"),
        Index("ix_categories_parent", "parent_id"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    sku = Column(String(100), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.product_categories.id", ondelete="RESTRICT"),
    )
    short_description = Column(Text)
    status = Column(String(20), nullable=False, server_default=text("'DRAFT'"))
    current_version_id = Column(UUID(as_uuid=True))
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        named_check("products_status_check", "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')"),
        ForeignKeyConstraint(
            ["current_version_id", "id"],
            ["app.product_versions.id", "app.product_versions.product_id"],
            name="fk_product_current_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        Index("ix_products_category", "category_id"),
        Index("ix_products_status", "status"),
    )


class ProductVersion(Base):
    __tablename__ = "product_versions"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number = Column(Integer, nullable=False)
    content_snapshot = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'DRAFT'"))
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    published_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app.admin_users.id", ondelete="SET NULL"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
    published_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("product_id", "version_number"),
        UniqueConstraint("id", "product_id"),
        named_check("product_versions_version_number_check", "version_number > 0"),
        named_check("product_versions_status_check", "status IN ('DRAFT', 'PUBLISHED', 'RETIRED')"),
        named_check("product_versions_check", 
            "(status = 'DRAFT' AND published_at IS NULL) OR "
            "(status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)"
        ),
        Index(
            "ix_product_versions_product",
            "product_id",
            text("version_number DESC"),
        ),
    )


class ProductMedia(Base):
    __tablename__ = "product_media"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=text("gen_random_uuid()"))
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app.products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_id = Column(UUID(as_uuid=True))
    media_type = Column(String(20), nullable=False)
    storage_key = Column(Text, nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(150), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(CHAR(64))
    display_order = Column(Integer, nullable=False, server_default=text("0"))
    alt_text = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["version_id", "product_id"],
            ["app.product_versions.id", "app.product_versions.product_id"],
            ondelete="RESTRICT",
        ),
        named_check("product_media_media_type_check", "media_type IN ('IMAGE', 'VIDEO', 'DOCUMENT')"),
        named_check("product_media_file_size_bytes_check", "file_size_bytes >= 0"),
        Index("ix_product_media_order", "product_id", "display_order"),
    )
