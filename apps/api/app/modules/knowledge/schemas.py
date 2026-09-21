from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)
    subject_id: UUID
    objective_ids: list[UUID] = Field(default_factory=list, max_length=10)
    k: int = Field(default=8, ge=1, le=20)


class RetrievedChunkOut(BaseModel):
    id: UUID
    source_title: str
    printed_page: int | None
    heading_path: str | None
    content_kind: str
    authority_tier: str
    excerpt: str  # short excerpt only (copyright)
    similarity: float | None
    aligned: bool


class SearchResponse(BaseModel):
    state: str
    chunks: list[RetrievedChunkOut]
