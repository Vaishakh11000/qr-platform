from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductMediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    version_id: UUID | None
    media_type: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str | None
    display_order: int
    alt_text: str | None
    created_at: datetime
