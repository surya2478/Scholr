"""The diagrams a lesson may carry, and the deterministic check each one must pass (AC-U14).

A model never draws. It picks a kind from the subject's own vocabulary and supplies the few numbers the picture
needs ("a Venn of the factors of 12 and 18"); everything drawn — the prime factors, the shared part, the
arrows, the ticks — is computed here, from those numbers, by SymPy and Pint. A diagram whose numbers do not
check out is dropped exactly like a worked example whose answer SymPy cannot reproduce.

Adding a kind means: a spec model, a `check` that returns what the drawing needs, and a component in
`apps/web/src/components/learn/diagrams/`. Subjects list the kinds they use in their own config, so no engine
code names a subject.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sympy import Rational, factorint, gcd, lcm, nsimplify

from app.tools import elements, units

MAX_VALUE = 100_000


class DiagramError(ValueError):
    """The numbers do not describe a picture we can draw and stand behind."""


@dataclass(frozen=True)
class Checked:
    """What the page draws: the kind, and the figures computed here rather than written by a model."""

    kind: str
    data: dict[str, Any]


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VennFactors(_Spec):
    """Two numbers side by side: shared prime factors in the middle (HCF), everything together (LCM)."""

    first: int = Field(ge=2, le=MAX_VALUE)
    second: int = Field(ge=2, le=MAX_VALUE)


class NumberLine(_Spec):
    """A line from `start` to `end` with `values` marked on it, and an optional shaded stretch."""

    start: float
    end: float
    values: list[float] = Field(default_factory=list, max_length=12)
    shade_from: float | None = None
    shade_to: float | None = None


class BarModel(_Spec):
    """A whole split into named parts — the bar model her book uses for ratio and fraction work."""

    total_label: str = Field(default="", max_length=60)
    parts: list[dict[str, Any]] = Field(min_length=2, max_length=8)


class RightTriangle(_Spec):
    """A right-angled triangle, drawn to scale from two sides."""

    base: float = Field(gt=0)
    height: float = Field(gt=0)
    hypotenuse: float | None = None
    base_label: str = Field(default="", max_length=24)
    height_label: str = Field(default="", max_length=24)
    hypotenuse_label: str = Field(default="", max_length=24)


class ForceArrows(_Spec):
    """Arrows on a body, with the resultant worked out here (Physics free-body sketch)."""

    body: str = Field(default="", max_length=40)
    forces: list[dict[str, Any]] = Field(min_length=1, max_length=6)
    unit: str = "N"


class Wave(_Spec):
    """One wave with its wavelength and amplitude marked; speed is checked against v = f λ when given."""

    wavelength_m: float = Field(gt=0)
    amplitude_cm: float = Field(gt=0)
    frequency_hz: float | None = Field(default=None, gt=0)
    speed_ms: float | None = Field(default=None, gt=0)


class RayDiagram(_Spec):
    """Light meeting a surface: reflected at the angle it arrived, or refracted by Snell's law."""

    behaviour: Literal["reflection", "refraction"]
    angle_of_incidence: float = Field(gt=0, lt=90)  # measured from the normal, as the syllabus does
    angle_of_refraction: float | None = Field(default=None, gt=0, lt=90)
    refractive_index: float | None = Field(default=None, gt=1, le=4)
    surface: str = Field(default="", max_length=30)  # "mirror", "glass block", "water"


class Circuit(_Spec):
    """A cell and its components in series or parallel, with the current worked out from Ohm's law."""

    emf_v: float = Field(gt=0, le=1000)
    arrangement: Literal["series", "parallel"] = "series"
    components: list[dict[str, Any]] = Field(min_length=1, max_length=4)
    current_a: float | None = Field(default=None, gt=0)


class CoordinateGrid(_Spec):
    """Axes with points plotted on them, optionally joined in the order given (a shape, a translation)."""

    x_min: float = -10
    x_max: float = 10
    y_min: float = -10
    y_max: float = 10
    points: list[dict[str, Any]] = Field(min_length=1, max_length=8)
    join: bool = False  # join the points in order, and close the shape when there are three or more


class StraightLineGraph(_Spec):
    """y = mx + c drawn across a range of x, with its intercept marked and any named points checked on it."""

    gradient: float
    intercept: float
    x_min: float = -6
    x_max: float = 6
    points: list[dict[str, Any]] = Field(default_factory=list, max_length=4)


class AtomStructure(_Spec):
    """One atom or simple ion: nucleus (protons and neutrons) and electron shells, all worked out from the element,
    its mass number and its charge."""

    element: str = Field(min_length=1, max_length=12)  # symbol or name: "Na", "sodium"
    mass_number: int = Field(ge=1, le=80)
    charge: int = Field(default=0, ge=-3, le=3)  # 0 for an atom; +1 for Na+, -2 for O2-


class ParticleBoxes(_Spec):
    """Boxes of particles, each drawn from the atoms in its particles; what each box is (element, compound or
    mixture) is worked out here and must agree with its label."""

    boxes: list[dict[str, Any]] = Field(min_length=1, max_length=4)


class PeriodicTable(_Spec):
    """The first four periods, with groups I–VIII and the transition elements; chosen groups or elements lit."""

    highlight_groups: list[int] = Field(default_factory=list, max_length=8)
    highlight_elements: list[str] = Field(default_factory=list, max_length=12)


SPECS: dict[str, type[_Spec]] = {
    "venn_factors": VennFactors,
    "number_line": NumberLine,
    "bar_model": BarModel,
    "right_triangle": RightTriangle,
    "force_arrows": ForceArrows,
    "wave": Wave,
    "coordinate_grid": CoordinateGrid,
    "straight_line_graph": StraightLineGraph,
    "ray_diagram": RayDiagram,
    "circuit": Circuit,
    "atom_structure": AtomStructure,
    "particle_boxes": ParticleBoxes,
    "periodic_table": PeriodicTable,
}
KINDS = frozenset(SPECS)
# Kinds whose numbers are illustrative rather than this lesson's own: a refraction angle, a cell's voltage or a
# wave's amplitude shows what the idea means, and each of these carries a physical law of its own (Snell's law,
# V = IR, the law of reflection, the resultant) that keeps it honest whatever the numbers. The rest — a Venn of
# two numbers, a bar model, a line graph — are about a particular case, and must use the lesson's own numbers.
# The Chemistry pictures are built wholly from the element table here, so any atom or particle drawn is a true one.
ILLUSTRATIVE = frozenset(
    {"ray_diagram", "circuit", "wave", "force_arrows", "atom_structure", "particle_boxes", "periodic_table"}
)
_DIRECTIONS = {"left": (-1.0, 0.0), "right": (1.0, 0.0), "up": (0.0, 1.0), "down": (0.0, -1.0)}


def _venn(spec: VennFactors) -> dict[str, Any]:
    first, second = factorint(spec.first), factorint(spec.second)
    shared = {p: min(first.get(p, 0), second.get(p, 0)) for p in set(first) & set(second)}
    only = lambda whole: {p: e - shared.get(p, 0) for p, e in whole.items() if e - shared.get(p, 0) > 0}  # noqa: E731
    return {
        "first": spec.first,
        "second": spec.second,
        "only_first": _powers(only(first)),
        "only_second": _powers(only(second)),
        "shared": _powers(shared),
        "hcf": int(gcd(spec.first, spec.second)),
        "lcm": int(lcm(spec.first, spec.second)),
    }


def _powers(factors: dict[int, int]) -> list[dict[str, int]]:
    return [{"prime": int(p), "power": int(e)} for p, e in sorted(factors.items())]


def _number_line(spec: NumberLine) -> dict[str, Any]:
    if spec.end <= spec.start:
        raise DiagramError("a number line must end after it starts")
    if any(not (spec.start <= v <= spec.end) for v in spec.values):
        raise DiagramError("every marked value must be on the line")
    shade = [spec.shade_from, spec.shade_to]
    if (shade[0] is None) != (shade[1] is None):
        raise DiagramError("a shaded stretch needs both ends")
    if shade[0] is not None and not (spec.start <= shade[0] <= shade[1] <= spec.end):  # type: ignore[operator]
        raise DiagramError("the shaded stretch must lie on the line, left to right")
    return {
        "start": spec.start,
        "end": spec.end,
        "values": spec.values,
        "shade_from": spec.shade_from,
        "shade_to": spec.shade_to,
    }


_PLACEHOLDER = re.compile(r"^(part|section|piece|item|bar)\s*\d*$", re.IGNORECASE)


def _bar_model(spec: BarModel) -> dict[str, Any]:
    parts = []
    for part in spec.parts:
        label = str(part.get("label", "")).strip()[:40]
        # "Part 1 / Part 2" is a diagram of nothing: a bar model's parts are the quantities being compared.
        if not label or _PLACEHOLDER.match(label):
            raise DiagramError("every part of a bar model needs a name of its own")
        try:
            value = float(part["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DiagramError("every part of a bar model needs a number") from exc
        if value <= 0:
            raise DiagramError("a part of a bar cannot be zero or negative")
        parts.append({"label": label, "value": value})
    total = sum(part["value"] for part in parts)
    return {"total_label": spec.total_label, "total": total, "parts": parts}


def _right_triangle(spec: RightTriangle) -> dict[str, Any]:
    computed = float(nsimplify(Rational(str(spec.base)) ** 2 + Rational(str(spec.height)) ** 2) ** 0.5)
    if spec.hypotenuse is not None and abs(spec.hypotenuse - computed) > max(0.01, 0.01 * computed):
        raise DiagramError("the three sides are not a right-angled triangle")
    return {
        "base": spec.base,
        "height": spec.height,
        "hypotenuse": round(computed, 4),
        "base_label": spec.base_label,
        "height_label": spec.height_label,
        "hypotenuse_label": spec.hypotenuse_label,
    }


def _force_arrows(spec: ForceArrows) -> dict[str, Any]:
    # Arrows on a body are forces. A current in amps or a potential difference in volts is not a force, however
    # neatly it would draw, so the unit must measure the same quantity as a newton.
    if not units.same_dimension(spec.unit, "N"):
        raise DiagramError(f"{spec.unit!r} does not measure force")
    arrows, x, y = [], 0.0, 0.0
    for force in spec.forces:
        direction = str(force.get("direction", "")).lower().strip()
        if direction not in _DIRECTIONS:
            raise DiagramError("each force points left, right, up or down")
        try:
            magnitude = float(force["magnitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DiagramError("each force needs a size") from exc
        if magnitude <= 0:
            raise DiagramError("a force arrow cannot be zero or negative")
        dx, dy = _DIRECTIONS[direction]
        x, y = x + dx * magnitude, y + dy * magnitude
        arrows.append(
            {"label": str(force.get("label", "")).strip()[:40], "magnitude": magnitude, "direction": direction}
        )
    return {
        "body": spec.body,
        "unit": units.display(spec.unit),
        "forces": arrows,
        # The resultant is worked out here, so the picture and the arithmetic can never disagree.
        "resultant": {"x": round(x, 4), "y": round(y, 4), "size": round((x * x + y * y) ** 0.5, 4)},
    }


def _wave(spec: Wave) -> dict[str, Any]:
    if spec.frequency_hz and spec.speed_ms:
        expected = spec.frequency_hz * spec.wavelength_m
        if abs(expected - spec.speed_ms) > max(0.01, 0.01 * expected):
            raise DiagramError("speed, frequency and wavelength do not agree (v = f λ)")
    return {
        "wavelength_m": spec.wavelength_m,
        "amplitude_cm": spec.amplitude_cm,
        "frequency_hz": spec.frequency_hz,
        "speed_ms": spec.speed_ms or (spec.frequency_hz * spec.wavelength_m if spec.frequency_hz else None),
    }


MAX_SPAN = 60  # a grid wider than this has ticks nobody can read on a phone


def _axes(spec: CoordinateGrid | StraightLineGraph, y_min: float, y_max: float) -> dict[str, Any]:
    """The window a graph is drawn in, with a tick spacing that keeps it readable."""
    x_span, y_span = spec.x_max - spec.x_min, y_max - y_min
    if x_span <= 0 or y_span <= 0:
        raise DiagramError("the axes must run left to right and bottom to top")
    if x_span > MAX_SPAN or y_span > MAX_SPAN:
        raise DiagramError("that window is too wide to label on a phone")
    step = lambda span: next(s for s in (1, 2, 5, 10, 20, 50) if span / s <= 12)  # noqa: E731
    return {
        "x_min": spec.x_min,
        "x_max": spec.x_max,
        "y_min": y_min,
        "y_max": y_max,
        "x_step": step(x_span),
        "y_step": step(y_span),
    }


def _point(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        x, y = float(raw["x"]), float(raw["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DiagramError("every point needs an x and a y") from exc
    return {"x": x, "y": y, "label": str(raw.get("label", "")).strip()[:24]}


def _coordinate_grid(spec: CoordinateGrid) -> dict[str, Any]:
    points = [_point(raw) for raw in spec.points]
    outside = [p for p in points if not (spec.x_min <= p["x"] <= spec.x_max and spec.y_min <= p["y"] <= spec.y_max)]
    if outside:
        raise DiagramError("every point must be inside the axes it is drawn on")
    return {**_axes(spec, spec.y_min, spec.y_max), "points": points, "join": spec.join}


def _equation(gradient: float, intercept: float) -> str:
    """ "y = 2x + 3", "y = -x", "y = 1/2x - 4" — written here so the picture and its label always agree."""
    m, c = nsimplify(Rational(str(gradient))), nsimplify(Rational(str(intercept)))
    term = "" if m == 0 else "x" if m == 1 else "-x" if m == -1 else f"{m}x"
    if m == 0:
        return f"y = {c}"
    if c == 0:
        return f"y = {term}"
    return f"y = {term} {'+' if c > 0 else '-'} {abs(c)}"


def _straight_line_graph(spec: StraightLineGraph) -> dict[str, Any]:
    at = lambda x: spec.gradient * x + spec.intercept  # noqa: E731
    ends = [{"x": spec.x_min, "y": at(spec.x_min)}, {"x": spec.x_max, "y": at(spec.x_max)}]
    points = [_point(raw) for raw in spec.points]
    off = [p for p in points if abs(p["y"] - at(p["x"])) > max(0.01, 0.01 * abs(p["y"]))]
    if off:
        raise DiagramError("a marked point is not on the line it is drawn on")
    ys = [end["y"] for end in ends] + [0.0, spec.intercept]
    low, high = min(ys), max(ys)
    pad = max(1.0, (high - low) * 0.1)
    return {
        **_axes(spec, round(low - pad, 3), round(high + pad, 3)),
        "gradient": spec.gradient,
        "intercept": spec.intercept,
        "equation": _equation(spec.gradient, spec.intercept),
        "ends": ends,
        "points": points,
    }


def _ray_diagram(spec: RayDiagram) -> dict[str, Any]:
    """Reflection: the angles are equal, and we say so. Refraction: Snell's law decides the second angle."""
    incidence = spec.angle_of_incidence
    if spec.behaviour == "reflection":
        if spec.angle_of_refraction is not None or spec.refractive_index is not None:
            raise DiagramError("a reflection has no refracted ray")
        return {
            "behaviour": "reflection",
            "surface": spec.surface or "mirror",
            "angle_in": incidence,
            "angle_out": incidence,  # the law of reflection, not the model's arithmetic
        }
    index = spec.refractive_index
    if index is None and spec.angle_of_refraction is None:
        raise DiagramError("a refraction needs a refractive index or the angle inside the material")
    if index is None:
        # n from the two angles: light entering a denser material bends towards the normal.
        if spec.angle_of_refraction >= incidence:  # type: ignore[operator]
            raise DiagramError("light entering a denser material bends towards the normal")
        index = math.sin(math.radians(incidence)) / math.sin(math.radians(spec.angle_of_refraction))  # type: ignore[arg-type]
    inside = math.degrees(math.asin(min(1.0, math.sin(math.radians(incidence)) / index)))
    if spec.angle_of_refraction is not None and abs(spec.angle_of_refraction - inside) > 1.0:
        raise DiagramError("those angles do not obey Snell's law")
    return {
        "behaviour": "refraction",
        "surface": spec.surface or "glass block",
        "angle_in": incidence,
        "angle_out": round(inside, 1),
        "refractive_index": round(index, 3),
        "critical_angle": round(math.degrees(math.asin(1 / index)), 1),
    }


_SUPPLY = re.compile(r"^(cell|battery|supply|power supply|source|emf)$", re.IGNORECASE)


def _circuit(spec: Circuit) -> dict[str, Any]:
    parts = []
    for component in spec.components:
        label = str(component.get("label", "")).strip()[:24]
        # The cell is drawn from `emf_v`. Listing it again as a resistance doubles the circuit's resistance
        # and teaches that a cell is a resistor.
        if _SUPPLY.match(label):
            raise DiagramError("the cell is not a component — give its voltage as emf_v")
        try:
            resistance = float(component["resistance_ohm"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DiagramError("every component needs a resistance in ohms") from exc
        if resistance <= 0:
            raise DiagramError("a resistance cannot be zero or negative")
        parts.append({"label": label or f"R{len(parts) + 1}", "resistance_ohm": resistance})
    if spec.arrangement == "series":
        total = sum(part["resistance_ohm"] for part in parts)
    else:
        total = 1 / sum(1 / part["resistance_ohm"] for part in parts)
    current = spec.emf_v / total
    if spec.current_a is not None and abs(spec.current_a - current) > max(0.01, 0.02 * current):
        raise DiagramError("that current does not follow from V = IR")
    return {
        "emf_v": spec.emf_v,
        "arrangement": spec.arrangement,
        "components": parts,
        # Worked out here: the picture's numbers and its arithmetic can never drift apart.
        "total_resistance_ohm": round(total, 3),
        "current_a": round(current, 3),
    }


def _element(text: str) -> elements.Element:
    found = elements.find(text)
    if found is None:
        raise DiagramError(f"{text!r} is not one of the first 36 elements")
    return found


def _atom_structure(spec: AtomStructure) -> dict[str, Any]:
    element = _element(spec.element)
    if element.z > elements.MAX_CONFIGURED:
        raise DiagramError("electron shells are drawn for proton numbers 1 to 20 only")
    neutrons = spec.mass_number - element.z
    # A real nucleus: hydrogen-1 has none; otherwise there are about as many neutrons as protons, never under
    # half as many or over twice (the first 20 elements' isotopes all fall inside this).
    if neutrons < 0 or (element.z > 1 and not element.z / 2 <= neutrons <= element.z * 2):
        raise DiagramError("that mass number is not a real isotope of this element")
    electrons = element.z - spec.charge
    return {
        "symbol": element.symbol,
        "name": element.name,
        "protons": element.z,
        "neutrons": neutrons,
        "electrons": electrons,
        "mass_number": spec.mass_number,
        "charge": spec.charge,
        "shells": elements.shells(electrons),
    }


_BOX_KINDS = ("element", "compound", "mixture")


def _particle_boxes(spec: ParticleBoxes) -> dict[str, Any]:
    boxes = []
    for box in spec.boxes:
        label = str(box.get("label", "")).strip()[:40]
        particles = box.get("particles")
        if not label or not isinstance(particles, list) or not 1 <= len(particles) <= 4:
            raise DiagramError("each box needs a label and one to four kinds of particle")
        drawn, symbols_by_particle = [], []
        for particle in particles:
            atoms = particle.get("atoms") if isinstance(particle, dict) else None
            count = particle.get("count", 1) if isinstance(particle, dict) else 0
            if not isinstance(atoms, list) or not 1 <= len(atoms) <= 5 or not isinstance(count, int):
                raise DiagramError("a particle is a list of one to five atoms, with a count")
            if not 1 <= count <= 8:
                raise DiagramError("draw one to eight of each particle")
            symbols = [_element(str(a)).symbol for a in atoms]
            drawn.append({"atoms": symbols, "count": count, "formula": _formula(symbols)})
            symbols_by_particle.append(symbols)
        kinds = {tuple(sorted(s)) for s in symbols_by_particle}
        if len(kinds) > 1:
            what = "mixture"
        elif len(set(symbols_by_particle[0])) == 1:
            what = "element"
        else:
            what = "compound"
        # The label must say what the box is: a "compound" label on a box of two elements teaches it backwards.
        named = [k for k in _BOX_KINDS if k in label.lower()]
        says = "mixture" if "mixture" in named else (named[0] if len(named) == 1 else None)
        if (says and what != says) or (named and not says and what == "mixture"):
            raise DiagramError(f"the box labelled {label!r} holds {'an' if what == 'element' else 'a'} {what}")
        boxes.append({"label": label, "classification": what, "particles": drawn})
    return {"boxes": boxes}


def _formula(symbols: list[str]) -> str:
    counts: dict[str, int] = {}
    for symbol in symbols:
        counts[symbol] = counts.get(symbol, 0) + 1
    return "".join(f"{s}{n if n > 1 else ''}" for s, n in counts.items())


def _periodic_table(spec: PeriodicTable) -> dict[str, Any]:
    groups = sorted(set(spec.highlight_groups))
    if any(not 1 <= g <= 8 for g in groups):
        raise DiagramError("groups run from I to VIII")
    lit = [_element(e).symbol for e in spec.highlight_elements]
    if not groups and not lit:
        raise DiagramError("light up at least one group or element")
    cells = [
        {"symbol": e.symbol, "z": e.z, "group": e.group, "period": e.period}
        for e in sorted(elements.ELEMENTS.values(), key=lambda e: e.z)
    ]
    return {"cells": cells, "highlight_groups": groups, "highlight_elements": lit, "group_names": elements.GROUP_NAMES}


_CHECKS = {
    "venn_factors": _venn,
    "number_line": _number_line,
    "bar_model": _bar_model,
    "right_triangle": _right_triangle,
    "force_arrows": _force_arrows,
    "wave": _wave,
    "coordinate_grid": _coordinate_grid,
    "straight_line_graph": _straight_line_graph,
    "ray_diagram": _ray_diagram,
    "circuit": _circuit,
    "atom_structure": _atom_structure,
    "particle_boxes": _particle_boxes,
    "periodic_table": _periodic_table,
}


def check(kind: str, data: dict[str, Any], *, allowed: frozenset[str] | set[str]) -> Checked:
    """Validate one proposed diagram and return what the page should draw.

    Raises :class:`DiagramError` for a kind this subject does not use, numbers that do not fit the kind, or
    numbers that contradict themselves.
    """
    if kind not in allowed:
        raise DiagramError(f"{kind!r} is not one of this subject's diagrams")
    if copies_example(kind, data):
        raise DiagramError("these are the example's numbers, not this lesson's")
    try:
        spec = SPECS[kind].model_validate(data)
    except ValidationError as exc:
        raise DiagramError(str(exc.errors()[0].get("msg", "the numbers do not fit this diagram"))) from exc
    return Checked(kind=kind, data=_CHECKS[kind](spec))  # type: ignore[arg-type]


DESCRIPTIONS = {
    "venn_factors": (
        "venn_factors — two numbers' prime factors in two overlapping circles: the shared part is the HCF, "
        'everything together is the LCM. data: {"first": 12, "second": 18}'
    ),
    "number_line": (
        "number_line — a line with values marked on it, and optionally a stretch shaded (inequalities, "
        'rounding, bounds). data: {"start": -5, "end": 5, "values": [-2, 3], "shade_from": -2, "shade_to": 3}'
    ),
    "bar_model": (
        "bar_model — one whole split into named parts (ratio, fractions, percentages). "
        'data: {"total_label": "£60 shared 2:3", "parts": [{"label": "Ann", "value": 24}, '
        '{"label": "Ben", "value": 36}]}'
    ),
    "right_triangle": (
        "right_triangle — a right-angled triangle drawn to scale from two sides (Pythagoras, trigonometry). "
        'data: {"base": 5, "height": 12, "hypotenuse": 13, "base_label": "5 cm", "height_label": "12 cm"}'
    ),
    "force_arrows": (
        "force_arrows — arrows on a body, each pointing left, right, up or down; the resultant is worked out "
        'for you. data: {"body": "box", "unit": "N", "forces": [{"label": "push", "magnitude": 50, '
        '"direction": "right"}, {"label": "friction", "magnitude": 10, "direction": "left"}]}'
    ),
    "wave": (
        "wave — one wave with its wavelength and amplitude marked; give frequency and speed only if the "
        'lesson does, and they must satisfy v = f λ. data: {"wavelength_m": 2, "amplitude_cm": 3, '
        '"frequency_hz": 50, "speed_ms": 100}'
    ),
    "coordinate_grid": (
        "coordinate_grid — axes with points plotted on them, joined in order when `join` is true (a shape, a "
        'translation, a reflection). data: {"x_min": -6, "x_max": 6, "y_min": -6, "y_max": 6, "join": true, '
        '"points": [{"x": 1, "y": 2, "label": "A"}, {"x": 4, "y": 2, "label": "B"}, {"x": 4, "y": 5, '
        '"label": "C"}]}'
    ),
    "ray_diagram": (
        "ray_diagram — light meeting a surface, with the angles measured from the normal as the syllabus does. "
        "Reflection needs only the angle it arrives at; refraction needs the refractive index, or the angle "
        "inside the material, and Snell's law is applied for you. "
        'data: {"behaviour": "refraction", '
        '"angle_of_incidence": 40, "refractive_index": 1.5, "surface": "glass block"}'
    ),
    "circuit": (
        "circuit — a cell and its components in series or parallel; the total resistance and the current are "
        'worked out for you from V = IR. data: {"emf_v": 6, "arrangement": "series", "components": '
        '[{"label": "lamp", "resistance_ohm": 4}, {"label": "resistor", "resistance_ohm": 8}]}'
    ),
    "atom_structure": (
        "atom_structure — one atom or simple ion drawn with its nucleus (protons and neutrons) and electron shells, "
        "all worked out for you from the element, its mass number and its charge (proton numbers 1 to 20). "
        'data: {"element": "Mg", "mass_number": 24, "charge": 0}'
    ),
    "particle_boxes": (
        "particle_boxes — up to four boxes of particles, each particle a list of atom symbols (O2 is "
        '["O", "O"], H2O is ["H", "H", "O"]); whether a box is an element, a compound or a mixture is worked out '
        'for you and must match its label. data: {"boxes": [{"label": "an element", "particles": '
        '[{"atoms": ["N", "N"], "count": 4}]}, {"label": "a compound", "particles": [{"atoms": ["C", "O", "O"], '
        '"count": 3}]}]}'
    ),
    "periodic_table": (
        "periodic_table — the first four periods with groups I to VIII and the transition elements; light up the "
        'groups or elements the lesson talks about. data: {"highlight_groups": [1, 7], "highlight_elements": ["Na"]}'
    ),
    "straight_line_graph": (
        "straight_line_graph — the line y = mx + c across a range of x, with its intercept marked and the "
        "equation written for you; any point you list must lie on the line. "
        'data: {"gradient": 2, "intercept": -3, "x_min": -4, "x_max": 4, "points": [{"x": 2, "y": 1, '
        '"label": "(2, 1)"}]}'
    ),
}


# The data shown in DESCRIPTIONS belongs to another lesson: a model that copies it out has chosen a picture of
# nothing. Rejected here so the prompt can keep showing a worked shape (19–20 Sep 2026: it copied all three).
EXAMPLES: dict[str, dict[str, Any]] = {
    "venn_factors": {"first": 12, "second": 18},
    "number_line": {"start": -5, "end": 5, "values": [-2, 3], "shade_from": -2, "shade_to": 3},
    "bar_model": {
        "total_label": "£60 shared 2:3",
        "parts": [{"label": "Ann", "value": 24}, {"label": "Ben", "value": 36}],
    },
    "right_triangle": {"base": 5, "height": 12, "hypotenuse": 13},
    "force_arrows": {
        "body": "box",
        "unit": "N",
        "forces": [
            {"label": "push", "magnitude": 50, "direction": "right"},
            {"label": "friction", "magnitude": 10, "direction": "left"},
        ],
    },
    "wave": {"wavelength_m": 2, "amplitude_cm": 3, "frequency_hz": 50, "speed_ms": 100},
    "coordinate_grid": {
        "x_min": -6,
        "x_max": 6,
        "y_min": -6,
        "y_max": 6,
        "join": True,
        "points": [{"x": 1, "y": 2}, {"x": 4, "y": 2}, {"x": 4, "y": 5}],
    },
    "straight_line_graph": {"gradient": 2, "intercept": -3, "x_min": -4, "x_max": 4, "points": [{"x": 2, "y": 1}]},
    "ray_diagram": {"behaviour": "refraction", "angle_of_incidence": 40, "refractive_index": 1.5},
    "circuit": {
        "emf_v": 6,
        "arrangement": "series",
        "components": [{"label": "lamp", "resistance_ohm": 4}, {"label": "resistor", "resistance_ohm": 8}],
    },
}


def _numbers(value: Any) -> tuple[float, ...]:
    if isinstance(value, dict):
        return tuple(n for item in value.values() for n in _numbers(item))
    if isinstance(value, (list, tuple)):
        return tuple(n for item in value for n in _numbers(item))
    return (float(value),) if isinstance(value, (int, float)) and not isinstance(value, bool) else ()


def copies_example(kind: str, data: dict[str, Any]) -> bool:
    """True if the proposed numbers are the ones the prompt used to show this kind's shape."""
    example = EXAMPLES.get(kind)
    return example is not None and sorted(_numbers(data)) == sorted(_numbers(example))


def vocabulary(kinds: Sequence[str]) -> str:
    """The prompt's list of diagrams, written from this module so the two can never drift apart."""
    return "\n".join(f"- {DESCRIPTIONS[kind]}" for kind in kinds if kind in DESCRIPTIONS)
