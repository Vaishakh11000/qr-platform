from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    ip_hash: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int
