"""Knowledge ingestion job.

Usage (from apps/api):
  uv run python -m app.jobs.ingest register            # register all manifest sources + text-layer pages
  uv run python -m app.jobs.ingest ocr --source collins-igcse-maths-4e [--pages 1-50] [--concurrency 6]
  uv run python -m app.jobs.ingest status
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import func, select

import app.models_registry  # noqa: F401
from app.core.config import get_settings
from app.core.db import get_session_factory, session_scope
from app.llm.factory import build_gateway
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Tenant
from app.modules.knowledge.extraction import RegisteredDocument, extract_text_layer, register_manifest, run_ocr
from app.modules.knowledge.manifest import load_all
from app.modules.knowledge.models import DocumentPage, KnowledgeDocument, Source
from app.modules.knowledge.ocr import OcrOptions
from app.modules.knowledge.postprocess import repair_json_escapes


def _parse_pages(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    pages: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            pages.extend(range(int(lo), int(hi) + 1))
        else:
            pages.append(int(part))
    return pages


def _tenant_id():  # noqa: ANN202
    with session_scope(user_id=None, role="system") as s:
        tenant = s.scalar(select(Tenant).order_by(Tenant.created_at))
        if tenant is None:
            raise SystemExit("no tenant: run app.seed.household first")
        return tenant.id


def register_all() -> list[RegisteredDocument]:
    settings = get_settings()
    subjects_dir = settings.resolve_path(settings.subjects_dir)
    tenant_id = _tenant_id()
    docs: list[RegisteredDocument] = []
    for manifest in load_all():
        with session_scope(user_id=None, role="system") as s:
            registered = register_manifest(s, tenant_id=tenant_id, manifest=manifest, subjects_dir=subjects_dir)
            for doc in registered:
                written = extract_text_layer(s, tenant_id=tenant_id, doc=doc) if doc.has_text_layer else 0
                flag = "new" if doc.created else "existing"
                layer = "text layer" if doc.has_text_layer else "needs OCR"
                print(f"{doc.source_key:32} {flag:8} {doc.page_count:4} pages  {layer:10} +{written} pages")
            docs.extend(registered)
    return docs


def ocr(source_key: str, pages: list[int] | None, concurrency: int) -> None:
    docs = {d.source_key: d for d in register_all()}
    if source_key not in docs:
        raise SystemExit(f"unknown source key: {source_key}")
    doc = docs[source_key]
    if doc.has_text_layer:
        raise SystemExit(f"{source_key} has a text layer; OCR not needed")
    src = next(src for manifest in load_all() for src in manifest.sources if src.key == source_key)
    options = OcrOptions(
        role=src.ocr_role, prompt=src.ocr_prompt, output=src.ocr_output, dpi=src.ocr_dpi, bands=src.ocr_bands
    )
    print(f"OCR {options}  postprocess={src.ocr_postprocess}", flush=True)

    def progress(done: int, total: int) -> None:
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total}", flush=True)

    report = run_ocr(
        get_session_factory(),
        build_gateway(),
        tenant_id=_tenant_id(),
        doc=doc,
        pages=pages,
        concurrency=concurrency,
        options=options,
        postprocess=src.ocr_postprocess,
        on_progress=progress,
    )
    print(
        f"requested={report.requested} written={report.written} failed={len(report.failed)} cost=${report.cost_usd:.2f}"
    )
    if report.stopped_reason == "quota_exceeded":
        print("STOPPED: OpenRouter account is out of credit. Top up, then re-run this command to resume.")
    elif report.stopped_reason:
        print(f"STOPPED: {report.stopped_reason}")
    if report.failed:
        print("failed pages:", sorted(report.failed))


def repair(source_key: str) -> None:
    """Apply deterministic repairs to already-stored OCR pages (idempotent; audited)."""
    with session_scope(user_id=None, role="system") as s:
        pages = s.scalars(
            select(DocumentPage)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentPage.document_id)
            .join(Source, Source.id == KnowledgeDocument.source_id)
            .where(Source.manifest_key == source_key, DocumentPage.extraction_method == "vision_ocr")
        ).all()
        fixed: list[int] = []
        for page in pages:
            text = repair_json_escapes(page.text)
            if text != page.text:
                page.text = text
                page.meta = {**(page.meta or {}), "repaired": ["repair_json_escapes"]}
                fixed.append(page.page_number)
        if fixed:
            s.add(
                AuditLog(
                    tenant_id=pages[0].tenant_id,
                    actor_role="system",
                    action="knowledge.pages_repaired",
                    entity_type="source",
                    meta={"source_key": source_key, "repair": "repair_json_escapes", "pages": sorted(fixed)},
                )
            )
    print(f"{source_key}: repaired {len(fixed)} of {len(pages)} OCR pages {sorted(fixed)}")


def status() -> None:
    with session_scope(user_id=None, role="system") as s:
        rows = s.execute(
            select(Source.manifest_key, KnowledgeDocument.page_count, func.count(DocumentPage.id))
            .join(KnowledgeDocument, KnowledgeDocument.source_id == Source.id)
            .outerjoin(DocumentPage, DocumentPage.document_id == KnowledgeDocument.id)
            .group_by(Source.manifest_key, KnowledgeDocument.page_count)
            .order_by(Source.manifest_key)
        ).all()
    for key, total, extracted in rows:
        print(f"{key:32} {extracted:4}/{total} pages extracted")


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="app.jobs.ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("register")
    p_ocr = sub.add_parser("ocr")
    p_ocr.add_argument("--source", required=True)
    p_ocr.add_argument("--pages")
    p_ocr.add_argument("--concurrency", type=int, default=6)
    sub.add_parser("status")
    p_repair = sub.add_parser("repair")
    p_repair.add_argument("--source", required=True)
    args = parser.parse_args(argv[1:])
    if args.cmd == "register":
        register_all()
    elif args.cmd == "ocr":
        ocr(args.source, _parse_pages(args.pages), args.concurrency)
    elif args.cmd == "repair":
        repair(args.source)
    else:
        status()


if __name__ == "__main__":
    main(sys.argv)
