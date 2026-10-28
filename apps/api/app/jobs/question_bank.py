"""Build the past-paper question bank from registered question papers and mark schemes.

Usage (from apps/api):
  uv run python -m app.jobs.question_bank [--only 0580-mj24-qp21] [--role paper_extractor_lite] [--model M]
      [--dry-run] [--concurrency 4]
  uv run python -m app.jobs.question_bank --recheck [--dry-run] [--only 0580-mj24-qp21]

--dry-run extracts without saving and compares the result with the items already in the bank for that paper
(screening a cheaper extractor). The report holds metrics only and goes to evals/reports/.
With --recheck, --dry-run reports what would be demoted/restored without changing any item.
A page that fails extraction is recorded; the paper then fails its checks, so none of its items are verified.

For subjects whose mark schemes are question tables (TABULAR_MARK_SCHEMES), the mark-scheme PDF is parsed by layout
(app.modules.assessment.mark_scheme). When the parse is usable, answers, marks and marking guidance come from it and
the LLM extracts question text only (prompt v2); otherwise the v1 flow runs unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT, get_settings
from app.core.db import session_scope
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext
from app.modules.assessment.mark_scheme import MarkSchemeTable, looks_tabular, parse_pdf
from app.modules.assessment.models import QuestionItem
from app.modules.assessment.past_papers import (
    EXTRACTOR_ROLE,
    ExtractedItem,
    PaperCheck,
    PaperInput,
    ReferenceItem,
    check_paper,
    check_paper_against_table,
    compare_extractions,
    extract_paper,
    item_status,
    merge_pages,
    parse_total_marks,
    recheck_bank_items,
    save_items,
)
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.knowledge.manifest import SourceIn, load_all
from app.modules.knowledge.models import DocumentPage, KnowledgeDocument, Source
from app.modules.knowledge.ocr import render_page_png

REPORTS_DIR = API_ROOT.parents[1] / "evals" / "reports"
SUBJECT_NOTES = {
    "igcse-maths": "Cambridge IGCSE Mathematics 0580. Objective codes are Collins textbook section numbers.",
    "igcse-sociology": (
        "Cambridge IGCSE Sociology 0495. Current units: Research methods 1.x; Identity: self and society 2.x; "
        "Social stratification and inequality 3.x; Family 4.x; Education 5.x; Crime, deviance and social control 6.x. "
        "Older papers map Theory and methods -> 1.x, Culture, identity and socialisation -> 2.x, Social inequality "
        "-> 3.x. Media has no current unit: use objective_codes []."
    ),
}


def paper_notes(subject_code: str, source: SourceIn) -> str:
    """Subject notes plus this paper's own manifest notes (series structure, calculator rules)."""
    return " ".join(x for x in (SUBJECT_NOTES[subject_code], source.title, source.notes or "") if x)


def without_off_syllabus_tags[T](
    merged: list[tuple[ExtractedItem, T]], untagged: list[str]
) -> list[tuple[ExtractedItem, T]]:
    """Drop the extractor's objective codes on questions the manifest marks as off the current syllabus.

    The prompt already says Media has no unit, but the model tagged old Media questions onto Research methods and
    Identity (22 Sep 2026), so the rule is applied here, in code. "4(e)" belongs to question 4."""
    off = set(untagged)
    return [
        (item.model_copy(update={"objective_codes": []}) if re.match(r"\d*", item.ref)[0] in off else item, pages)
        for item, pages in merged
    ]


def without_cross_unit_tags[T](
    merged: list[tuple[ExtractedItem, T]], question_units: dict[str, str]
) -> list[tuple[ExtractedItem, T]]:
    """Keep only the objective codes that sit in the unit this paper gives that question number.

    The extractor tags by theme, so a Crime question that mentions official statistics collects Research Methods
    codes as well (27 Oct 2026: 67 such tags on Paper 2 Q3 alone, one of which put a crime essay under "the
    positivist approach"). A paper's structure is printed on the paper, so the manifest states it and this drops
    anything outside it. A question number the manifest does not mention is left alone, and a manifest may name
    one question in full to give it a different unit from the rest of its section.
    """
    if not question_units:
        return merged
    out = []
    for item, pages in merged:
        # A full ref ("1(f)") wins over its question number ("1"), for the one-off a syllabus change leaves
        # behind: MJ23's Paper 1 Section A was "theory and methods", so its Q1(f) is a theory question and
        # belongs to unit 2, where consensus and conflict now live (the user's decision, 28 Oct 2026).
        unit = question_units.get(item.ref) or question_units.get(re.match(r"\d*", item.ref)[0])
        if unit is None:
            out.append((item, pages))
            continue
        kept = [code for code in item.objective_codes if code.split(".")[0] == unit]
        out.append((item.model_copy(update={"objective_codes": kept}) if kept != item.objective_codes else item, pages))
    return out


# Papers where every question is compulsory, so marks must add up to the printed total.
ALL_COMPULSORY = {"igcse-maths"}
# Subjects whose mark schemes are Question/Answer/Marks/Partial Marks tables (Sociology's are prose level descriptors).
# TODO: move to a subject-config field alongside ALL_COMPULSORY.
TABULAR_MARK_SCHEMES = {"igcse-maths"}


def _mark_scheme_table(job: PaperJob) -> MarkSchemeTable | None:
    """The parsed mark-scheme table, or None when the subject has none or the parse is not usable (fall back to v1)."""
    if job.subject_code not in TABULAR_MARK_SCHEMES:
        return None
    settings = get_settings()
    table = parse_pdf(settings.resolve_path(settings.subjects_dir) / job.ms.file)
    return table if looks_tabular(table) else None


@dataclass(frozen=True)
class PaperJob:
    subject_code: str
    qp: SourceIn
    ms: SourceIn


def _jobs(only: str | None) -> list[PaperJob]:
    jobs: list[PaperJob] = []
    for manifest in load_all():
        by_key = {s.key: s for s in manifest.sources}
        for key, src in by_key.items():
            if src.content_kind != "question":
                continue
            ms_key = key.replace("-qp", "-ms")
            if ms_key not in by_key:
                raise SystemExit(f"no mark scheme for {key}")
            if only and key != only:
                continue
            jobs.append(PaperJob(manifest.subject, src, by_key[ms_key]))
    return jobs


def _pages(s, source_key: str) -> tuple[UUID, UUID, dict[int, str]]:  # noqa: ANN001
    row = s.execute(
        select(Source.id, KnowledgeDocument.id)
        .join(KnowledgeDocument, KnowledgeDocument.source_id == Source.id)
        .where(Source.manifest_key == source_key)
    ).one()
    texts = dict(
        s.execute(select(DocumentPage.page_number, DocumentPage.text).where(DocumentPage.document_id == row[1])).all()
    )
    if not texts:
        raise SystemExit(f"{source_key}: no extracted pages — run app.jobs.ingest register")
    return row[0], row[1], texts


def run_job(job: PaperJob, *, role: str = EXTRACTOR_ROLE, model: str | None = None, dry_run: bool = False) -> str:
    settings = get_settings()
    subjects_dir = settings.resolve_path(settings.subjects_dir)
    with session_scope(user_id=None, role="system") as s:
        subject = s.scalar(select(Subject).where(Subject.code == job.subject_code))
        assert subject is not None
        qp_source_id, _, qp_texts = _pages(s, job.qp.key)
        _, _, ms_texts = _pages(s, job.ms.key)
        rows = s.execute(
            select(LearningObjective.code, LearningObjective.statement, LearningObjective.id, Topic.id, Topic.name)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .where(Topic.subject_id == subject.id)
            .order_by(Topic.code, LearningObjective.code)
        ).all()
        tenant_id = s.scalar(select(Source.tenant_id).where(Source.id == qp_source_id))
        subject_id = subject.id
    objective_map = {code: (oid, tid) for code, _, oid, tid, _ in rows}
    objectives_prompt = "\n".join(f"{code}: {stmt} ({topic})" for code, stmt, _, _, topic in rows)

    pdf = Path(subjects_dir / job.qp.file)
    images = {n: render_page_png(pdf, n - 1, dpi=130) for n in qp_texts if n != 1}
    syllabus = job.qp.key.split("-")[0]
    paper = PaperInput(
        syllabus_code=syllabus,
        component=job.qp.component or "",
        series=(job.qp.exam_series or "").upper(),
        label=job.qp.title,
        subject_notes=paper_notes(job.subject_code, job.qp),
        page_texts=qp_texts,
        page_images=images,
        mark_scheme_text="\n".join(ms_texts[n] for n in sorted(ms_texts)),
        objectives_prompt=objectives_prompt,
        expected_total=parse_total_marks(qp_texts.get(1, "")) if job.subject_code in ALL_COMPULSORY else None,
    )
    table = _mark_scheme_table(job)
    answer_source = "mark_scheme_table" if table is not None else "extractor"
    gateway = build_gateway()
    ctx = CallContext(request_id=f"qbank:{job.qp.key}", tenant_id=tenant_id)
    extraction = extract_paper(gateway, ctx, paper, role=role, models=[model] if model else None, table=table)
    merged = without_off_syllabus_tags(merge_pages(extraction.pages), job.qp.untagged_questions)
    merged = without_cross_unit_tags(merged, job.qp.question_units)
    items = [m[0] for m in merged]
    if table is not None:
        check = check_paper_against_table(
            items, table, expected_total=paper.expected_total, unmatched_refs=extraction.unmatched_refs
        )
    else:
        check = check_paper(items, expected_total=paper.expected_total, mark_scheme_text=paper.mark_scheme_text)
    check.issues.extend(f"page_failed:{n}:{code}" for n, code in sorted(extraction.failed_pages.items()))
    marks_total = sum(m[0].marks for m in merged)
    item_issue_count = sum(len(v) for v in check.item_issues.values())
    model_used = extraction.model or (model or load_roles().role(role).model)

    if dry_run:
        verified_refs = {item.ref for item, _ in merged if item_status(item, check, objective_map)[0] == "verified"}
        verified = len(verified_refs)
        prefix = f"{paper.syllabus_code}/{paper.component}/{paper.series}/Q"
        with session_scope(user_id=None, role="system") as s:
            reference = [
                ReferenceItem(
                    ref=row.source_ref.removeprefix(prefix),
                    marks=row.marks,
                    answer_type=str(row.answer_spec.get("type", "")),
                    answer=str(row.answer_spec.get("answer", "")),
                    exact=row.answer_spec.get("exact"),
                )
                for row in s.scalars(select(QuestionItem).where(QuestionItem.source_ref.like(prefix + "%")))
            ]
        comparison = compare_extractions(reference, [m[0] for m in merged], verified_refs=verified_refs)
        # Item-level view: which items pass their own checks if paper-level issues (failed pages, marks total) are
        # set aside — shows whether the extractor's per-item output is safe even when a paper fails as a whole.
        if table is not None:
            item_check = PaperCheck(item_issues=check.item_issues)
        else:
            item_check = check_paper(items, expected_total=None, mark_scheme_text=paper.mark_scheme_text)
        item_level_refs = {
            item.ref for item, _ in merged if item_status(item, item_check, objective_map)[0] == "verified"
        }
        item_level = compare_extractions(reference, [m[0] for m in merged], verified_refs=item_level_refs)
        report = {
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "paper": job.qp.key,
            "role": role,
            "model": model_used,
            "prompt": f"past_paper_extract/{extraction.prompt_version}",
            "answer_source": answer_source,
            "mark_scheme_table": (
                {
                    "rows": len(table.rows),
                    "marks_total": table.total_marks,
                    "parse_issues": table.issues,
                    "unmatched_extractor_refs": extraction.unmatched_refs,
                }
                if table is not None
                else None
            ),
            "items": len(merged),
            "verified": verified,
            "marks_total": marks_total,
            "expected_total": paper.expected_total,
            "paper_issues": check.issues,
            "item_issues": item_issue_count,
            "failed_pages": extraction.failed_pages,
            "cost_usd": round(extraction.cost_usd, 4),
            "comparison_with_bank": comparison.as_dict(),
            "item_level_verified": len(item_level_refs),
            "item_level_verified_disagreements": item_level.verified_disagreements,
            "differing_fields": item_level.differences,  # field names only; values go to private storage
        }
        # Values (question and mark-scheme content) stay in gitignored private storage for manual review.
        ref_by = {r.ref: r for r in reference}
        cand_by = {item.ref: item for item, _ in merged}
        details = {
            ref: {
                "fields": fields,
                "candidate_verified_item_level": ref in item_level_refs,
                "reference": {
                    "marks": ref_by[ref].marks,
                    "type": ref_by[ref].answer_type,
                    "answer": ref_by[ref].answer,
                    "exact": ref_by[ref].exact,
                },
                "candidate": {
                    "marks": cand_by[ref].marks,
                    "type": cand_by[ref].answer_type,
                    "answer": cand_by[ref].answer,
                    "exact": cand_by[ref].exact_value,
                },
            }
            for ref, fields in item_level.differences.items()
        }
        private_dir = settings.resolve_path(settings.private_content_dir) / "extract_eval"
        private_dir.mkdir(parents=True, exist_ok=True)
        private_path = (
            private_dir / f"{job.qp.key}_{(model or role).replace('/', '_')}_{datetime.now(UTC):%Y%m%d-%H%M}.json"
        )
        private_path.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = f"{datetime.now(UTC):%Y%m%d-%H%M}"
        path = REPORTS_DIR / f"extract_{job.qp.key}_{model_used.replace('/', '_')}_{stamp}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        c = comparison
        return (
            f"{job.qp.key:18} DRY RUN model={model_used} answers={answer_source} items={len(merged)} "
            f"verified={verified} marks={marks_total}/{paper.expected_total} paper_issues={check.issues} "
            f"item_issues={item_issue_count} "
            f"cost=${extraction.cost_usd:.3f}\n"
            f"  vs bank: matched {c.matched}/{c.reference_items} (missing {c.missing_refs}, extra {c.extra_refs}) "
            f"marks {c.marks_agree} type {c.type_agree} answer {c.answer_agree} "
            f"exact {c.exact_agree}/{c.exact_compared}\n"
            f"  verified but disagreeing with bank: {c.verified_disagreements}\n"
            f"  item level (paper issues set aside): verified {len(item_level_refs)}, "
            f"disagreeing with bank {item_level.verified_disagreements}\n  report: {path}\n"
            f"  differences with values (private): {private_path}"
        )

    with session_scope(user_id=None, role="system") as s:
        saved, verified = save_items(
            s,
            tenant_id=tenant_id,
            subject_id=subject_id,
            source_id=qp_source_id,
            paper=paper,
            merged=merged,
            check=check,
            objective_map=objective_map,
            calculator_allowed=True if job.subject_code == "igcse-maths" else None,
            model=model_used,
            prompt_version=extraction.prompt_version,
            answers_from_table=table is not None,
        )
        s.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_role="system",
                action="assessment.question_bank_import",
                entity_type="source",
                entity_id=qp_source_id,
                meta={
                    "saved": saved,
                    "verified": verified,
                    "paper_issues": check.issues,
                    "model": model_used,
                    "answer_source": answer_source,
                },
            )
        )
    return (
        f"{job.qp.key:18} answers={answer_source} items={saved:3} verified={verified:3} marks={marks_total:4} "
        f"expected={paper.expected_total} paper_issues={check.issues} item_issues={item_issue_count} "
        f"cost=${extraction.cost_usd:.3f}"
    )


def recheck_job(job: PaperJob, *, apply: bool = True) -> str:
    """Deterministic re-check of a paper's stored items (no LLM calls). apply=False changes nothing."""
    syllabus = job.qp.key.split("-")[0]
    prefix = f"{syllabus}/{job.qp.component or ''}/{(job.qp.exam_series or '').upper()}/Q"
    table = _mark_scheme_table(job)
    with session_scope(user_id=None, role="system") as s:
        _, _, ms_texts = _pages(s, job.ms.key)
        tenant_id = s.scalar(select(Source.tenant_id).where(Source.manifest_key == job.qp.key))
        demoted, restored = recheck_bank_items(
            s,
            prefix=prefix,
            mark_scheme_text="\n".join(ms_texts[n] for n in sorted(ms_texts)),
            table=table,
            apply=apply,
        )
        if apply and (demoted or restored):
            s.add(
                AuditLog(
                    tenant_id=tenant_id,
                    actor_role="system",
                    action="assessment.question_bank_recheck",
                    entity_type="source",
                    meta={
                        "prefix": prefix,
                        "demoted": demoted,
                        "restored": restored,
                        "against": "mark_scheme_table" if table is not None else "mark_scheme_text",
                    },
                )
            )
    mode = "recheck" if apply else "recheck (dry run, nothing changed)"
    against = "table" if table is not None else "text"
    return (
        f"{job.qp.key:18} {mode} against={against}: demoted {len(demoted)} {demoted} | "
        f"restored {len(restored)} {sorted(restored)}"
    )


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.question_bank")
    parser.add_argument("--only")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--role", default=EXTRACTOR_ROLE, help="LLM role for extraction (see roles.yaml)")
    parser.add_argument("--model", help="override the role's model")
    parser.add_argument("--dry-run", action="store_true", help="save nothing (extraction: compare with the bank)")
    parser.add_argument("--recheck", action="store_true", help="re-run deterministic checks on stored items; no LLM")
    args = parser.parse_args(argv[1:])
    jobs = _jobs(args.only)
    if args.recheck:
        for job in jobs:
            print(recheck_job(job, apply=not args.dry_run), flush=True)
        return
    extractor = args.model or load_roles().role(args.role).model
    print(f"extractor: role={args.role} model={extractor} dry_run={args.dry_run}", flush=True)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for line in pool.map(partial(run_job, role=args.role, model=args.model, dry_run=args.dry_run), jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main(sys.argv)
