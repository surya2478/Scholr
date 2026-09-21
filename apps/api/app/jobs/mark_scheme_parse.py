"""Parse mark-scheme question tables deterministically and summarise them (no LLM).

Usage (from apps/api):
  uv run python -m app.jobs.mark_scheme_parse [--only 0580-mj24-ms21] [--bank] [--dump]

Prints, per mark scheme: pages with a table, rows, marks total vs the printed total on the matching question paper
cover, rows with empty answers, rows with unreadable marks, parse issues. Mark schemes without a question table (e.g.
prose level descriptors) are reported as "no table".

--bank  compares parsed marks and answer numbers with the stored question-bank items of the paper (read-only).
        Metrics go to evals/reports/; the values of any disagreement go to content/private/mark_scheme_eval/.
--dump  writes the parsed rows (answer text included) to content/private/mark_scheme_eval/ for manual review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT, get_settings
from app.core.db import session_scope
from app.modules.assessment.mark_scheme import MarkSchemeTable, looks_tabular, numbers, parse_pdf
from app.modules.assessment.models import QuestionItem
from app.modules.assessment.past_papers import parse_total_marks
from app.modules.knowledge.manifest import load_all

REPORTS_DIR = API_ROOT.parents[1] / "evals" / "reports"


def printed_total(question_paper: Path) -> int | None:
    with pymupdf.open(question_paper) as doc:
        return parse_total_marks(doc[0].get_text()) if doc.page_count else None


def question_paper_marks(question_paper: Path) -> list[int]:
    """Bracketed mark allocations "[n]" on the question pages (cover excluded), in printed order."""
    with pymupdf.open(question_paper) as doc:
        return [int(m) for page in list(doc)[1:] for m in re.findall(r"\[(\d{1,2})\]", page.get_text())]


def bank_agreement(table: MarkSchemeTable, prefix: str) -> tuple[dict[str, object], dict[str, object]]:
    """(metrics, private details) comparing the parsed table with stored bank items for one paper."""
    rows = table.by_ref()
    with session_scope(user_id=None, role="system") as s:
        items = [
            (
                r.source_ref.removeprefix(prefix),
                r.verification_status,
                r.marks,
                str((r.answer_spec or {}).get("answer", "")),
            )
            for r in s.scalars(
                select(QuestionItem).where(
                    QuestionItem.source_ref.like(prefix + "%"), QuestionItem.origin == "past_paper"
                )
            )
        ]
    metrics: dict[str, object] = {"bank_items": len(items)}
    details: dict[str, object] = {}
    verified = [i for i in items if i[1] == "verified"]
    missing = sorted(ref for ref, *_ in items if ref not in rows)
    marks_disagree: list[str] = []
    numbers_equal = numbers_subset = 0
    answer_disagree: list[str] = []
    for ref, _, marks, answer in verified:
        row = rows.get(ref)
        if row is None:
            continue
        if row.marks != marks:
            marks_disagree.append(ref)
            details.setdefault(ref, {})["marks"] = {"bank": marks, "parsed": row.marks}  # type: ignore[index]
        bank_numbers, parsed_numbers = numbers(answer), numbers(row.answer)
        numbers_equal += bank_numbers == parsed_numbers
        if bank_numbers <= parsed_numbers:
            numbers_subset += 1
        else:
            answer_disagree.append(ref)
            details.setdefault(ref, {})["answer"] = {  # type: ignore[index]
                "bank": answer,
                "parsed": row.answer,
                "parsed_method": row.method,
                "bank_numbers_not_in_parsed": sorted(bank_numbers - parsed_numbers),
            }
    metrics.update(
        {
            "verified_items": len(verified),
            "bank_refs_missing_from_table": missing,
            "table_refs_missing_from_bank": sorted(set(rows) - {ref for ref, *_ in items}),
            "verified_marks_agree": len(verified) - len(marks_disagree) - sum(1 for i in verified if i[0] not in rows),
            "verified_marks_disagree": marks_disagree,
            "verified_answer_numbers_equal": numbers_equal,
            "verified_answer_numbers_subset": numbers_subset,
            "verified_answer_disagree": answer_disagree,
        }
    )
    return metrics, details


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.mark_scheme_parse")
    parser.add_argument("--only", help="mark-scheme manifest key, e.g. 0580-mj24-ms21")
    parser.add_argument("--bank", action="store_true", help="compare with stored bank items (read-only)")
    parser.add_argument("--dump", action="store_true", help="write parsed rows to private storage")
    args = parser.parse_args(argv[1:])
    settings = get_settings()
    subjects_dir = settings.resolve_path(settings.subjects_dir)
    private_dir = settings.resolve_path(settings.private_content_dir) / "mark_scheme_eval"
    stamp = f"{datetime.now(UTC):%Y%m%d-%H%M}"
    report: dict[str, object] = {"created_at": datetime.now(UTC).isoformat(timespec="seconds"), "papers": {}}
    private: dict[str, object] = {}
    for manifest in load_all():
        by_key = {s.key: s for s in manifest.sources}
        for key, src in by_key.items():
            if src.content_kind != "mark_scheme" or (args.only and key != args.only):
                continue
            table = parse_pdf(subjects_dir / src.file)
            if not looks_tabular(table):
                found = 0 if table is None else len(table.rows)
                print(f"{key:18} no table (prose mark scheme or unreadable layout; rows={found})", flush=True)
                report["papers"][key] = {"table": False, "rows": found}  # type: ignore[index]
                continue
            assert table is not None
            qp = by_key.get(key.replace("-ms", "-qp"))
            expected = printed_total(subjects_dir / qp.file) if qp else None
            unparsed = [row.ref for row in table.rows if row.marks is None]
            qp_marks = question_paper_marks(subjects_dir / qp.file) if qp else []
            row_marks = [row.marks for row in table.rows]
            sequence_ok = row_marks == qp_marks
            summary: dict[str, object] = {
                "table": True,
                "pages": table.pages,
                "rows": len(table.rows),
                "refs": [row.ref for row in table.rows],
                "marks_total": table.total_marks,
                "printed_total": expected,
                # Parsed per-row marks in order equal the "[n]" allocations printed on the question paper.
                "marks_sequence_matches_question_paper": sequence_ok,
                "question_paper_allocations": len(qp_marks),
                "marks_unparsed": unparsed,
                "empty_answers": table.empty_answers(),
                "rows_with_method_lines": [row.ref for row in table.rows if row.method],
                "rows_with_diagrams": [row.ref for row in table.rows if "diagram" in row.notation],
                "issues": table.issues,
            }
            line = (
                f"{key:18} rows={len(table.rows):3} marks={table.total_marks}/{expected} "
                f"{'OK' if table.total_marks == expected else 'MISMATCH'} "
                f"per-row marks vs qp [n]: {'MATCH' if sequence_ok else 'DIFF'} ({len(qp_marks)} allocations) "
                f"empty_answers={table.empty_answers()} "
                f"diagrams={[row.ref for row in table.rows if 'diagram' in row.notation]} "
                f"marks_unparsed={unparsed} issues={table.issues}"
            )
            if args.bank and qp is not None:
                prefix = f"{key.split('-')[0]}/{qp.component}/{(qp.exam_series or '').upper()}/Q"
                metrics, details = bank_agreement(table, prefix)
                summary["bank"] = metrics
                private[f"{key}:bank_disagreements"] = details
                line += (
                    f"\n  vs bank: verified {metrics['verified_items']} marks_agree {metrics['verified_marks_agree']} "
                    f"marks_disagree {metrics['verified_marks_disagree']} "
                    f"numbers_equal {metrics['verified_answer_numbers_equal']} "
                    f"numbers_subset {metrics['verified_answer_numbers_subset']} "
                    f"answer_disagree {metrics['verified_answer_disagree']} "
                    f"missing {metrics['bank_refs_missing_from_table']}"
                )
            if args.dump:
                private[key] = [asdict(row) for row in table.rows]
            report["papers"][key] = summary  # type: ignore[index]
            print(line, flush=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"mark_scheme_parse_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report (metrics only): {path}")
    if private:
        private_dir.mkdir(parents=True, exist_ok=True)
        private_path = private_dir / f"parse_{stamp}.json"
        private_path.write_text(json.dumps(private, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"values (private): {private_path}")


if __name__ == "__main__":
    main(sys.argv)
