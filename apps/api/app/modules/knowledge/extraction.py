"""Register manifest sources and extract per-page text (text layer or vision OCR).

Extraction is resumable: pages already stored in document_page are skipped.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import set_rls_context
from app.llm.gateway import CallContext, LLMError, LLMGateway
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import Curriculum, Subject
from app.modules.knowledge.chunking import detect_printed_labels
from app.modules.knowledge.manifest import ManifestFile
from app.modules.knowledge.models import DocumentPage, KnowledgeDocument, Source
from app.modules.knowledge.ocr import OcrOptions, OcrResult, has_text_layer, ocr_page
from app.modules.knowledge.postprocess import apply_postprocess

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegisteredDocument:
    source_key: str
    source_id: UUID
    document_id: UUID
    title: str
    path: Path
    page_count: int
    has_text_layer: bool
    created: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def register_manifest(
    s: Session, *, tenant_id: UUID, manifest: ManifestFile, subjects_dir: Path
) -> list[RegisteredDocument]:
    subject = s.scalar(select(Subject).where(Subject.code == manifest.subject))
    if subject is None:
        raise ValueError(f"unknown subject {manifest.subject!r}: seed the curriculum first")
    curriculum = s.scalar(select(Curriculum).where(Curriculum.code == manifest.curriculum))

    registered: list[RegisteredDocument] = []
    for src in manifest.sources:
        path = subjects_dir / src.file
        if not path.is_file():
            raise FileNotFoundError(f"manifest {src.key}: file not found: {path}")

        source = s.scalar(select(Source).where(Source.manifest_key == src.key))
        values = {
            "title": src.title,
            "publisher": src.publisher,
            "edition": src.edition,
            "owner": src.owner,
            "licence": src.licence,
            "authority_tier": src.authority_tier,
            "acquired_via": src.acquired_via,
            "private": src.private,
            "subject_id": subject.id,
            "curriculum_id": curriculum.id if curriculum else None,
            "exam_series": src.exam_series,
            "version": src.component,
            "default_content_kind": src.content_kind,
            "notes": src.notes,
        }
        if source is None:
            source = Source(tenant_id=tenant_id, manifest_key=src.key, **values)
            s.add(source)
        else:
            for k, v in values.items():
                setattr(source, k, v)
        s.flush()

        sha = _sha256(path)
        doc = s.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id, KnowledgeDocument.sha256 == sha)
        )
        created = doc is None
        if doc is None:
            with pymupdf.open(path) as pdf:
                pages = int(pdf.page_count)
            doc = KnowledgeDocument(
                tenant_id=tenant_id,
                source_id=source.id,
                storage_uri=f"subjects/{src.file}",
                sha256=sha,
                content_type="application/pdf",
                page_count=pages,
                has_text_layer=has_text_layer(path),
            )
            s.add(doc)
            s.flush()
            s.add(
                AuditLog(
                    tenant_id=tenant_id,
                    actor_role="system",
                    action="knowledge.document_registered",
                    entity_type="knowledge_document",
                    entity_id=doc.id,
                    meta={"source_key": src.key, "sha256": sha, "pages": pages},
                )
            )
        registered.append(
            RegisteredDocument(
                source_key=src.key,
                source_id=source.id,
                document_id=doc.id,
                title=src.title,
                path=path,
                page_count=int(doc.page_count or 0),
                has_text_layer=bool(doc.has_text_layer),
                created=created,
            )
        )
    return registered


def existing_pages(s: Session, document_id: UUID) -> set[int]:
    return set(s.scalars(select(DocumentPage.page_number).where(DocumentPage.document_id == document_id)))


def extract_text_layer(s: Session, *, tenant_id: UUID, doc: RegisteredDocument) -> int:
    """Store text-layer text for every page not yet extracted. Returns pages written."""
    done = existing_pages(s, doc.document_id)
    written = 0
    with pymupdf.open(doc.path) as pdf:
        for index in range(pdf.page_count):
            number = index + 1
            if number in done:
                continue
            s.add(
                DocumentPage(
                    tenant_id=tenant_id,
                    document_id=doc.document_id,
                    page_number=number,
                    text=pdf[index].get_text("text", sort=True),
                    extraction_method="text_layer",
                )
            )
            written += 1
    s.flush()
    label_text_layer_pages(s, doc.document_id)
    return written


def label_text_layer_pages(s: Session, document_id: UUID) -> int:
    """Fill in printed page labels the text layer does not carry (chunking.detect_printed_labels), so textbook
    chunks can be tagged to objectives by printed page. Only unlabelled text-layer pages change. Returns labelled."""
    rows = s.scalars(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id, DocumentPage.extraction_method == "text_layer"
        )
    ).all()
    labels = detect_printed_labels([(row.page_number, row.text) for row in rows])
    changed = 0
    for row in rows:
        if row.printed_page_label is None and row.page_number in labels:
            row.printed_page_label = labels[row.page_number]
            changed += 1
    s.flush()
    return changed


@dataclass
class OcrReport:
    requested: int = 0
    written: int = 0
    failed: dict[int, str] = field(default_factory=dict)
    cost_usd: float = 0.0
    stopped_reason: str | None = None


def run_ocr(
    session_factory: sessionmaker[Session],
    gateway: LLMGateway,
    *,
    tenant_id: UUID,
    doc: RegisteredDocument,
    pages: list[int] | None = None,
    concurrency: int = 6,
    options: OcrOptions | None = None,
    postprocess: Sequence[str] = (),
    on_progress: Callable[[int, int], None] | None = None,
) -> OcrReport:
    """OCR pages (1-based numbers) not yet stored. Each page is committed as soon as it completes."""
    opts = options or OcrOptions()
    with session_factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        done = existing_pages(s, doc.document_id)
    wanted = pages or list(range(1, doc.page_count + 1))
    todo = [p for p in wanted if p not in done and 1 <= p <= doc.page_count]
    report = OcrReport(requested=len(todo))
    ctx = CallContext(request_id=f"ocr:{doc.source_key}", tenant_id=tenant_id)

    def work(number: int) -> OcrResult:
        return ocr_page(gateway, ctx, pdf_path=doc.path, page_index=number - 1, source_title=doc.title, options=opts)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(work, n): n for n in todo}
        for i, fut in enumerate(as_completed(futures), start=1):
            number = futures[fut]
            try:
                result = fut.result()
            except LLMError as exc:
                report.failed[number] = exc.code
                log.warning("OCR failed for %s page %s: %s", doc.source_key, number, exc.code)
                if exc.code in ("quota_exceeded", "not_configured"):
                    # Every remaining page would fail the same way; stop and let a later run resume.
                    report.stopped_reason = exc.code
                    for pending in futures:
                        pending.cancel()
                    break
                continue
            with session_factory() as s, s.begin():
                set_rls_context(s, user_id=None, role="system")
                s.add(
                    DocumentPage(
                        tenant_id=tenant_id,
                        document_id=doc.document_id,
                        page_number=number,
                        printed_page_label=result.printed_page_label,
                        text=apply_postprocess(result.markdown, postprocess),
                        extraction_method="vision_ocr",
                        extraction_model=result.model,
                        prompt_version=f"{result.prompt_name}/{result.prompt_version}",
                        meta={**result.meta, "postprocess": list(postprocess)},
                    )
                )
            report.written += 1
            report.cost_usd += result.cost_usd
            if on_progress:
                on_progress(i, len(todo))
    return report
