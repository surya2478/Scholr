"""Screen OCR settings (role/model, prompt, output format, DPI, bands) against pages already transcribed.

Usage (from apps/api):
  uv run python -m app.jobs.ocr_eval --source collins-igcse-maths-4e \
      [--role page_ocr_math] [--prompt page_ocr_math_md] [--output markdown] [--dpi 200] [--bands 2] \
      [--model google/gemini-2.5-flash-lite] [--sample 12 | --pages 13,15,19] [--seed 7] [--no-postprocess]

Options not given come from the source's manifest entry, so a bare run screens the configured settings.
Nothing is written to document_page. The report holds metrics only (no textbook text) and goes to evals/reports/;
candidate and reference texts for spot checks go to gitignored content/private/ocr_eval/.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT, get_settings
from app.core.db import session_scope
from app.jobs.ingest import _parse_pages
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext, LLMError
from app.llm.models import LlmCall
from app.modules.knowledge.manifest import load_all
from app.modules.knowledge.models import DocumentPage, KnowledgeDocument, Source
from app.modules.knowledge.ocr import OcrOptions, OcrResult, ocr_page
from app.modules.knowledge.ocr_compare import PageComparison, compare, summarise
from app.modules.knowledge.postprocess import apply_postprocess

REPORTS_DIR = API_ROOT.parents[1] / "evals" / "reports"


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.ocr_eval")
    parser.add_argument("--source", required=True)
    parser.add_argument("--role")
    parser.add_argument("--prompt")
    parser.add_argument("--output", choices=["json", "markdown"])
    parser.add_argument("--dpi", type=int)
    parser.add_argument("--bands", type=int)
    parser.add_argument("--model", help="override the role's model")
    parser.add_argument("--sample", type=int, default=12)
    parser.add_argument("--pages")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--no-postprocess", action="store_true", help="skip the manifest's ocr_postprocess steps")
    args = parser.parse_args(argv[1:])

    settings = get_settings()
    src = next((s for m in load_all() for s in m.sources if s.key == args.source), None)
    if src is None:
        raise SystemExit(f"unknown source key: {args.source}")
    pdf_path = settings.resolve_path(settings.subjects_dir) / src.file
    options = OcrOptions(
        role=args.role or src.ocr_role,
        prompt=args.prompt or src.ocr_prompt,
        output=args.output or src.ocr_output,
        dpi=args.dpi or src.ocr_dpi,
        bands=args.bands or src.ocr_bands,
        models=(args.model,) if args.model else None,
    )
    postprocess = [] if args.no_postprocess else list(src.ocr_postprocess)
    candidate_model = args.model or load_roles().role(options.role).model

    with session_scope(user_id=None, role="system") as s:
        doc = s.execute(
            select(KnowledgeDocument.id, KnowledgeDocument.page_count, Source.tenant_id, Source.title)
            .join(Source, Source.id == KnowledgeDocument.source_id)
            .where(Source.manifest_key == args.source)
        ).one_or_none()
        if doc is None:
            raise SystemExit(f"{args.source} is not registered: run app.jobs.ingest register")
        stored = s.execute(
            select(DocumentPage.page_number, DocumentPage.text, DocumentPage.extraction_model).where(
                DocumentPage.document_id == doc.id, DocumentPage.extraction_method == "vision_ocr"
            )
        ).all()
        reference_models = sorted({row.extraction_model for row in stored if row.extraction_model})
        reference_cost = s.scalar(
            select(func.avg(LlmCall.cost_usd)).where(
                LlmCall.role == "page_ocr", LlmCall.status == "ok", LlmCall.model.in_(reference_models)
            )
        )

    wanted = set(_parse_pages(args.pages) or [])
    pool = sorted(
        (r for r in stored if r.extraction_model != candidate_model and (not wanted or r.page_number in wanted)),
        key=lambda r: r.page_number,
    )
    if not pool:
        raise SystemExit("no stored OCR pages from another model to compare against")
    sample = pool if wanted else random.Random(args.seed).sample(pool, min(args.sample, len(pool)))

    run_label = (
        f"{args.source}_{options.prompt}_{options.output}_dpi{options.dpi}_b{options.bands}_"
        f"{candidate_model.replace('/', '_')}_{datetime.now(UTC):%Y%m%d-%H%M}"
    )
    save_dir = settings.resolve_path(settings.private_content_dir) / "ocr_eval" / run_label
    save_dir.mkdir(parents=True, exist_ok=True)
    gateway = build_gateway()
    ctx = CallContext(request_id=f"ocr_eval:{args.source}", tenant_id=doc.tenant_id)
    rows: list[PageComparison] = []
    costs: list[float] = []
    tokens_out: list[int] = []
    stopped: str | None = None

    def work(page_number: int) -> OcrResult:
        return ocr_page(
            gateway, ctx, pdf_path=pdf_path, page_index=page_number - 1, source_title=doc.title, options=options
        )

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {executor.submit(work, row.page_number): row for row in sample}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                result = fut.result()
            except LLMError as exc:
                print(f"  page {row.page_number}: {exc.code}", flush=True)
                if exc.code in ("quota_exceeded", "not_configured"):
                    stopped = exc.code
                    for pending in futures:
                        pending.cancel()
                    break
                continue
            markdown = apply_postprocess(result.markdown, postprocess)
            comparison = compare(row.page_number, row.text, markdown)
            rows.append(comparison)
            costs.append(result.cost_usd)
            tokens_out.append(result.output_tokens)
            (save_dir / f"{row.page_number:04}.candidate.md").write_text(markdown, encoding="utf-8")
            (save_dir / f"{row.page_number:04}.reference.md").write_text(row.text, encoding="utf-8")
            recall = "  -  " if comparison.math_recall is None else f"{comparison.math_recall:.3f}"
            print(
                f"  page {row.page_number:4}  content {comparison.content_f1:.3f}  maths recall {recall}  "
                f"latex {comparison.candidate_math_segments}/{comparison.reference_math_segments}  "
                f"leaks {comparison.unicode_leaks}  escape damage {comparison.escape_damage}  ${result.cost_usd:.4f}",
                flush=True,
            )

    if stopped:
        print("STOPPED: OpenRouter account is out of credit." if stopped == "quota_exceeded" else f"STOPPED: {stopped}")
    if not rows:
        raise SystemExit("no pages compared")

    summary = summarise(rows)
    remaining = (doc.page_count or 0) - len(stored)
    cost_per_page = sum(costs) / len(costs)
    report = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": args.source,
        "options": {**asdict(options), "postprocess": postprocess},
        "candidate_model": candidate_model,
        "reference_models": reference_models,
        "seed": args.seed,
        "summary": asdict(summary),
        "candidate_cost_per_page_usd": round(cost_per_page, 5),
        "reference_cost_per_page_usd": round(float(reference_cost), 5) if reference_cost is not None else None,
        "candidate_mean_output_tokens": round(sum(tokens_out) / len(tokens_out)),
        "remaining_pages": remaining,
        "projected_remaining_cost_usd": round(cost_per_page * remaining, 2),
        "lowest_pages": [asdict(r) for r in sorted(rows, key=lambda r: (r.math_recall or 1.0, r.content_f1))[:5]],
        "pages": [asdict(r) for r in sorted(rows, key=lambda r: r.page_number)],
        "note": "Reference is another model's transcription, not ground truth. Spot-check lowest_pages by eye.",
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"ocr_{run_label}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"\n{summary.verdict}: pages={summary.pages} content mean={summary.mean_content_f1}"
        f" min={summary.min_content_f1} | maths recall mean={summary.mean_math_recall}"
        f" | latex ratio={summary.math_segment_ratio}"
        f" | unicode leaks={summary.unicode_leaks} | escape damage={summary.escape_damage}"
    )
    print(
        f"cost/page candidate=${cost_per_page:.4f} reference=${report['reference_cost_per_page_usd']} "
        f"remaining {remaining} pages ~${report['projected_remaining_cost_usd']}"
    )
    print(f"spot-check texts (private): {save_dir}")
    print(f"report: {path}")


if __name__ == "__main__":
    main(sys.argv)
