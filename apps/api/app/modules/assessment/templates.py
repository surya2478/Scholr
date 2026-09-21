"""Parametric question templates with SymPy-verified answers (ARCHITECTURE §11, AC-E1).

A template picks parameters deterministically from a seed, computes the exact answer with SymPy, formats the answer a
student would write (3 significant figures unless the template asks for an exact value), then runs the same
deterministic answer checker the marker uses. Only items whose printed answer the checker accepts are kept, and they
carry ``answer_spec.sympy_verified = true`` (required by a database constraint before a template item can be verified).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import sympy
import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.tools.answer_check import check_final_answer
from app.tools.math_sympy import round_sig

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "subject_configs" / "templates"
GENERATOR_VERSION = "templates_v1"
_SAFE = {"gcd": sympy.gcd, "lcm": sympy.lcm, "Rational": sympy.Rational, "sqrt": sympy.sqrt, "pi": sympy.pi}


class TemplateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    objective: str
    marks: int = Field(ge=1, le=6)
    difficulty: int = Field(ge=1, le=5)
    command_word: str
    stem: str
    params: dict[str, list[int | float]]
    derived: dict[str, str] = Field(default_factory=dict)
    exact: str
    accuracy: Literal["sf3", "exact"]
    answer_format: Literal["decimal", "fraction"] = "decimal"
    mark_scheme: str


class TemplateFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    templates: list[TemplateSpec]


@dataclass(frozen=True)
class GeneratedItem:
    template_id: str
    seed: int
    objective_code: str
    marks: int
    difficulty: int
    command_word: str
    stem: str
    answer: str
    answer_spec: dict[str, Any]
    mark_scheme: str
    verified: bool
    issues: list[str] = field(default_factory=list)

    @property
    def source_ref(self) -> str:
        return f"template/{self.template_id}/{self.seed}"


def load_templates(config_key: str, directory: Path = TEMPLATES_DIR) -> TemplateFile:
    return TemplateFile.model_validate(yaml.safe_load((directory / f"{config_key}.yaml").read_text(encoding="utf-8")))


def _sympify(expression: str, values: dict[str, sympy.Expr]) -> sympy.Expr:
    return sympy.sympify(expression, locals={**_SAFE, **values}, rational=True)


def _display(value: sympy.Expr) -> str:
    if value.is_Integer:
        return str(int(value))
    if value.is_Rational:
        return str(Decimal(int(value.p)) / Decimal(int(value.q))).rstrip("0").rstrip(".")
    return str(value)


def _terminates_within(exact: sympy.Expr, figures: int = 8) -> bool:
    """Same convention as the answer checker: a short terminating decimal must be given exactly, not rounded."""
    if not exact.is_Rational:
        return False
    q = int(exact.q)
    for p in (2, 5):
        while q % p == 0:
            q //= p
    value = Decimal(int(exact.p)) / Decimal(int(exact.q))
    return q == 1 and value == round_sig(value, figures)


def _printed_answer(exact: sympy.Expr, spec: TemplateSpec) -> str:
    if spec.accuracy == "exact" or _terminates_within(exact):
        if spec.answer_format == "fraction" and exact.is_Rational and not exact.is_Integer:
            return f"{exact.p}/{exact.q}"
        return _display(exact)
    rounded = round_sig(Decimal(str(sympy.N(exact, 30))), 3)
    return format(rounded, "f")  # keep significant trailing zeros (e.g. 30.0 is 3 s.f.)


def generate(spec: TemplateSpec, seed: int) -> GeneratedItem:
    rng = random.Random(f"{spec.id}:{seed}")
    values: dict[str, sympy.Expr] = {
        name: sympy.nsimplify(rng.choice(options)) for name, options in spec.params.items()
    }
    for name, expression in spec.derived.items():
        values[name] = _sympify(expression, values)
    issues: list[str] = []
    try:
        exact = sympy.nsimplify(_sympify(spec.exact, values))
    except (sympy.SympifyError, TypeError, ValueError, ZeroDivisionError):
        exact, issues = sympy.nan, ["exact_not_computable"]
    if not issues and (not exact.is_real or not exact.is_finite):
        issues.append("exact_not_real")
    shown = {name: _display(v) for name, v in values.items()}
    answer = _printed_answer(exact, spec) if not issues else ""
    answer_spec: dict[str, Any] = {
        "type": "numeric",
        "answer": answer,
        "exact": str(exact),
        "accuracy": spec.accuracy,
        "accept_ranges": [],
    }
    if not issues:
        verdict = check_final_answer(answer, answer_spec, command_word=spec.command_word)
        if verdict.status != "correct":
            issues.append(f"checker_{verdict.status}")
    verified = not issues
    answer_spec["sympy_verified"] = verified
    return GeneratedItem(
        template_id=spec.id,
        seed=seed,
        objective_code=spec.objective,
        marks=spec.marks,
        difficulty=spec.difficulty,
        command_word=spec.command_word,
        stem=spec.stem.format(**shown),
        answer=answer,
        answer_spec=answer_spec,
        mark_scheme=spec.mark_scheme.format(**shown, answer=answer),
        verified=verified,
        issues=issues,
    )
