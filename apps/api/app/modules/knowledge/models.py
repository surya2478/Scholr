from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import EMBEDDING_DIM, Base, IdMixin, TenantScoped, TimestampMixin

AUTHORITY_TIERS = ("A", "B", "C", "D", "E")
CONTENT_KINDS = (
    "syllabus",
    "explanation",
    "definition",
    "worked_example",
    "exercise",
    "question",
    "mark_scheme",
    "examiner_report",
    "school_material",
    "student_note",
)


class Source(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "source"
    __table_args__ = (
        CheckConstraint("authority_tier in ('A','B','C','D','E')", name="authority_tier"),
        CheckConstraint(
            "ingestion_status in ('pending','extracting','extracted','chunked','embedded','failed')",
            name="ingestion_status",
        ),
    )
    manifest_key: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str | None] = mapped_column(String(200))
    edition: Mapped[str | None] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(200))
    licence: Mapped[str] = mapped_column(Text)
    authority_tier: Mapped[str] = mapped_column(String(1))
    acquired_via: Mapped[str] = mapped_column(String(200))
    private: Mapped[bool] = mapped_column(default=True)
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("subject.id"))
    curriculum_id: Mapped[UUID | None] = mapped_column(ForeignKey("curriculum.id"))
    version: Mapped[str | None] = mapped_column(String(64))
    exam_series: Mapped[str | None] = mapped_column(String(32))
    default_content_kind: Mapped[str] = mapped_column(String(32))
    ingestion_status: Mapped[str] = mapped_column(String(16), default="pending")
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class KnowledgeDocument(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "knowledge_document"
    __table_args__ = (UniqueConstraint("source_id", "sha256"),)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"), index=True)
    storage_uri: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(16), default="en")
    page_count: Mapped[int | None] = mapped_column(Integer)
    has_text_layer: Mapped[bool | None]


class DocumentPage(IdMixin, TimestampMixin, TenantScoped, Base):
    """Extracted text per page (text layer or OCR), kept so chunking can be re-run cheaply."""

    __tablename__ = "document_page"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_document.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    printed_page_label: Mapped[str | None] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(32))  # text_layer | vision_ocr
    extraction_model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class KnowledgeChunk(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        Index("ix_knowledge_chunk_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_knowledge_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_document.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("subject.id"), index=True)
    topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("topic.id"))
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    content_kind: Mapped[str] = mapped_column(String(32))
    authority_tier: Mapped[str] = mapped_column(String(1))
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(heading_path,'') || ' ' || content)", persisted=True)
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class RetrievalLog(IdMixin, TenantScoped, Base):
    __tablename__ = "retrieval_log"
    student_id: Mapped[UUID | None] = mapped_column(ForeignKey("student.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    query: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    state: Mapped[str] = mapped_column(String(16))
    top_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
