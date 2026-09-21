"""Architecture rules checked in CI.

AC-A2 / AC-X2: engine code has no subject-specific branches; subject behaviour comes from
subject_configs/*.yaml — including whether Scholr teaches the subject at all (``taught_here``).
AC-S5 (static half): log calls never pass conversation text, answers or questions, and engine code does not print.
The runtime half of AC-S5 is tests/integration/test_tutoring.py::test_logs_carry_no_conversation_or_answer_text.
"""

from __future__ import annotations

import ast
import io
import tokenize
from collections.abc import Iterator
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
ENGINE_DIRS = ("core", "llm", "modules", "tools")

SUBJECT_WORDS = frozenset(
    {"math", "maths", "mathematics", "sociology", "physics", "chemistry", "biology", "0580", "0495", "0625", "0620"}
)
LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
LEARNING_TEXT_NAMES = frozenset(
    {
        "content",
        "message",
        "messages",
        "text",
        "answer",
        "final_answer",
        "working",
        "stem",
        "reply",
        "statement",
        "prompt",
        "transcription",
        "excerpts",
    }
)


def _files(dirs: tuple[str, ...] = ENGINE_DIRS) -> list[Path]:
    return sorted(p for d in dirs for p in (APP / d).rglob("*.py"))


def _string_literals(path: Path) -> Iterator[tuple[int, str]]:
    for tok in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline):
        if tok.type != tokenize.STRING:
            continue
        try:
            value = ast.literal_eval(tok.string)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, str):
            yield tok.start[0], value


def test_engine_code_names_no_subject() -> None:  # AC-A2
    offenders = [
        f"{path.relative_to(APP)}:{line} {value!r}"
        for path in _files()
        for line, value in _string_literals(path)
        if value.strip().lower() in SUBJECT_WORDS or value.strip().lower().startswith(("igcse-", "iit-"))
    ]
    assert offenders == [], "subject behaviour belongs in subject_configs/*.yaml"


def test_engine_code_does_not_compare_subjects_with_literals() -> None:  # AC-A2
    offenders = []
    for path in _files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Compare) or not all(isinstance(op, ast.Eq | ast.NotEq) for op in node.ops):
                continue
            sides = [node.left, *node.comparators]
            literal = any(isinstance(n, ast.Constant) and isinstance(n.value, str) for n in sides)
            subject = any(
                not isinstance(n, ast.Constant) and "subject" in (src := ast.unparse(n).lower()) and "type" not in src
                for n in sides
            )
            if literal and subject:
                offenders.append(f"{path.relative_to(APP)}:{node.lineno} {ast.unparse(node)}")
    assert offenders == [], "branch on a subject config field instead"


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
    }


def test_log_calls_carry_no_learning_text() -> None:  # AC-S5
    offenders = []
    for path in _files(("core", "llm", "modules", "tools", "jobs", "seed")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS
            ):
                continue
            owner = ast.unparse(node.func.value).lower()
            if not (owner in {"log", "logger", "logging"} or owner.endswith(("_log", "_logger"))):
                continue
            arguments = [*node.args, *(k.value for k in node.keywords)]
            leaked = set().union(*(_names(a) for a in arguments)) & LEARNING_TEXT_NAMES if arguments else set()
            if leaked:
                offenders.append(f"{path.relative_to(APP)}:{node.lineno} {sorted(leaked)}")
    assert offenders == []


def test_engine_code_does_not_print() -> None:  # AC-S5: output goes through logging, which the rules above cover
    offenders = [
        f"{path.relative_to(APP)}:{node.lineno}"
        for path in _files()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
    ]
    assert offenders == []
