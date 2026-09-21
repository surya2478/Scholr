"""Examiner reports -> short, attributed points per question (AC-R6).

Splits each Principal Examiner Report into per-question segments in code (``examiner_reports.segment_report``),
asks Flash-Lite to paraphrase each question's segments in one call, and keeps only points that pass the guard:
short, our own words (no run of 8 words from the report), attributable. Only components that have items in
the question bank are sent, since nothing else could ever be shown.

Re-runs skip segments whose text and prompt version are unchanged.

Usage (from apps/api):
  uv run python -m app.jobs.examiner_insights                          # estimate only, no calls
  uv run python -m app.jobs.examiner_insights --run [--only 0495-mj25-er] [--force]
  uv run python -m app.jobs.examiner_insights --subject igcse-maths    # estimate for Maths

Counts go to evals/reports/ (no report text, no points).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import session_scope
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext, LLMError
from app.llm.prompts import default_registry
from app.modules.assessment import examiner_reports as er
from app.modules.assessment import service as assessment
from app.modules.assessment.models import QuestionItem
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import Subject
from app.modules.knowledge.models import DocumentPage, KnowledgeDocument, Source

REPORTS = API_ROOT.parents[1] / "evals" / "reports"
# Flash-Lite list prices ($/M tokens, OpenRouter). The estimate uses ~4 chars per token, plus the prompt.
PRICE_IN, PRICE_OUT = 0.10, 0.40
PROMPT_TOKENS = 700
OUT_TOKENS_PER_SEGMENT = 150


@dataclass(frozen=True)
class Report:
    source_id: UUID
    tenant_id: UUID
    subject_id: UUID
    key: str
    title: str
    series: str
    segments: tuple[er.ReportSegment, ...]


@dataclass
class Group:
    report: Report
    label: str
    segments: list[er.ReportSegment]

    @property
    def chars(self) -> int:
        return sum(len(s.text) for s in self.segments)


@dataclass
class Tally:
    calls: int = 0
    failed: int = 0
    segments: int = 0
    kept: int = 0
    copied: int = 0
    too_long: int = 0
    bad_ref: int = 0
    duplicate: int = 0
    unknown_blocks: int = 0
    empty_segments: int = 0
    cost_usd: float = 0.0
    by_kind: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def load_reports(subject_code: str, only: str | None) -> list[Report]:
    with session_scope(user_id=None, role="system") as s:
        subject = s.scalar(select(Subject).where(Subject.code == subject_code))
        if subject is None:
            raise SystemExit(f"unknown subject {subject_code}")
        query = select(Source).where(Source.subject_id == subject.id, Source.default_content_kind == "examiner_report")
        if only:
            query = query.where(Source.manifest_key == only)
        reports = []
        for source in s.scalars(query.order_by(Source.manifest_key)):
            pages = dict(
                s.execute(
                    select(DocumentPage.page_number, DocumentPage.text)
                    .join(KnowledgeDocument, KnowledgeDocument.id == DocumentPage.document_id)
                    .where(KnowledgeDocument.source_id == source.id)
                ).all()
            )
            if not pages:
                print(f"{source.manifest_key}: no extracted pages — run app.jobs.ingest register", flush=True)
                continue
            series = (source.exam_series or "").upper()
            # Only papers the bank holds: a point about any other paper could never be shown.
            banked = {
                tuple(ref.split("/")[:2])
                for ref in s.scalars(
                    select(QuestionItem.source_ref).where(
                        QuestionItem.subject_id == subject.id, QuestionItem.source_ref.like(f"%/{series}/Q%")
                    )
                )
                if ref
            }
            segments = tuple(seg for seg in er.segment_report(pages) if (seg.syllabus_code, seg.component) in banked)
            reports.append(
                Report(source.id, source.tenant_id, subject.id, source.manifest_key, source.title, series, segments)
            )
        return reports


def groups_for(report: Report, *, force: bool, prompt_version: str) -> list[Group]:
    with session_scope(user_id=None, role="system") as s:
        stored = assessment.stored_insight_segments(s, report.source_id)
    pending = [seg for seg in report.segments if force or stored.get(seg.key) != (seg.sha, prompt_version)]
    grouped: dict[tuple[str, str], list[er.ReportSegment]] = defaultdict(list)
    for seg in pending:
        grouped[(seg.component, seg.question_number or "paper")].append(seg)
    groups = []
    for (component, question), segs in grouped.items():
        where = "key messages and general comments" if question == "paper" else f"comments on Question {question}"
        groups.append(Group(report, f"{report.title}, Paper {component}: {where}", segs))
    return groups


def estimate_usd(groups: list[Group]) -> float:
    tokens_in = sum(PROMPT_TOKENS + g.chars / 4 for g in groups)
    tokens_out = sum(OUT_TOKENS_PER_SEGMENT * len(g.segments) for g in groups)
    return (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1_000_000


def run_group(group: Group, model: str | None) -> Tally:
    tally = Tally()
    report = group.report
    known = [
        seg.question_ref for seg in report.segments if seg.question_ref and seg.component == group.segments[0].component
    ]
    gateway = build_gateway()
    ctx = CallContext(request_id=f"er:{report.key}:{group.segments[0].key}", tenant_id=report.tenant_id)
    tally.calls += 1
    try:
        result = er.paraphrase(
            gateway, ctx, paper_label=group.label, segments=group.segments, models=[model] if model else None
        )
    except LLMError as exc:
        tally.failed += 1
        print(f"  {report.key} {group.segments[0].key}: failed ({exc.code})", flush=True)
        return tally
    tally.cost_usd += result.cost_usd
    tally.unknown_blocks += result.unknown_blocks
    with session_scope(user_id=None, role="system") as s:
        for seg in group.segments:
            guarded = er.guard(seg, result.by_segment.get(seg.key, []), known_refs=known)
            tally.segments += 1
            tally.kept += len(guarded.kept)
            tally.copied += guarded.copied
            tally.too_long += guarded.too_long
            tally.bad_ref += guarded.bad_ref
            tally.duplicate += guarded.duplicate
            tally.empty_segments += not guarded.kept
            for point in guarded.kept:
                tally.by_kind[point.kind] += 1
            assessment.replace_segment_insights(
                s,
                tenant_id=report.tenant_id,
                source_id=report.source_id,
                subject_id=report.subject_id,
                report_title=report.title,
                exam_series=report.series,
                segment=seg,
                points=guarded.kept,
                prompt_version=result.prompt_version,
                model=result.model,
            )
    return tally


def merge(tallies: list[Tally]) -> Tally:
    total = Tally()
    for part in tallies:
        for name, value in part.__dict__.items():
            if name == "by_kind":
                for kind, n in value.items():
                    total.by_kind[kind] += n
            else:
                setattr(total, name, getattr(total, name) + value)
    return total


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.examiner_insights")
    parser.add_argument("--subject", default="igcse-sociology")
    parser.add_argument("--only", help="one report's manifest key, e.g. 0495-mj25-er")
    parser.add_argument("--run", action="store_true", help="make the calls; without it, print the estimate only")
    parser.add_argument("--force", action="store_true", help="redo segments already stored")
    parser.add_argument("--model", help="override the role's model")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args(argv[1:])

    prompt_version = default_registry().get(er.PROMPT).version
    reports = load_reports(args.subject, args.only)
    all_groups: list[Group] = []
    for report in reports:
        groups = groups_for(report, force=args.force, prompt_version=prompt_version)
        components = sorted({seg.component for seg in report.segments})
        pending = sum(len(g.segments) for g in groups)
        print(
            f"{report.key:14} papers in bank {components} segments={len(report.segments)} "
            f"to do={pending} calls={len(groups)}",
            flush=True,
        )
        all_groups.extend(groups)
    model = args.model or load_roles().role(er.ROLE).model
    print(
        f"total: {len(all_groups)} calls, estimate ${estimate_usd(all_groups):.3f} "
        f"(model {model}, prompt {er.PROMPT}/{prompt_version})",
        flush=True,
    )
    if not args.run or not all_groups:
        return

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        tally = merge(list(pool.map(lambda g: run_group(g, args.model), all_groups)))

    with session_scope(user_id=None, role="system") as s:
        for report in reports:
            s.add(
                AuditLog(
                    tenant_id=report.tenant_id,
                    actor_role="system",
                    action="assessment.examiner_insights_import",
                    entity_type="source",
                    entity_id=report.source_id,
                    meta={"prompt_version": prompt_version, "model": model, "segmenter": er.SEGMENTER_VERSION},
                )
            )
    summary = {
        "subject": args.subject,
        "reports": [r.key for r in reports],
        "prompt": f"{er.PROMPT}/{prompt_version}",
        "segmenter": er.SEGMENTER_VERSION,
        "model": model,
        **{k: v for k, v in tally.__dict__.items() if k != "by_kind"},
        "by_kind": dict(tally.by_kind),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"examiner_insights_{args.subject}_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"report: {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv)
