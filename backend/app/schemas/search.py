from typing import Literal
from uuid import UUID

from pydantic import BaseModel


SearchPage = Literal[
    "Products",
    "Categories",
    "Regions",
    "QR Codes",
    "QR Batches",
    "Location Policies",
    "Forms",
    "Audit Logs",
    "Administration",
]


class SearchResult(BaseModel):
    id: UUID
    kind: str
    title: str
    detail: str | None
    page: SearchPage
    target_key: str | None = None


class SearchResponse(BaseModel):
    query: str
    items: list[SearchResult]
