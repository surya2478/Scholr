"""Deterministic (no-AI) parser for Cambridge IGCSE Mathematics mark-scheme question tables.

The table is read by layout, not from the plain text layer:
- the header row ("Question", "Answer", "Marks", "Partial Marks") names the columns; the thin vertical rules drawn
  beside those words give the exact column boundaries (header-word midpoints are the fallback);
- a row starts at the horizontal rule above each Question-column ref and runs to the next ref's rule, so merged
  cells (a method line and a final-answer line under one ref) stay in one row, and content above the first ref on
  a page continues the last row of the previous page;
- a stacked fraction is a short horizontal stroke with glyphs sitting directly on it and hanging directly below
  it; it becomes one inline token "a/b" (parenthesised when either side is not a simple term);
- tall bracket pieces (Symbol font) enclosing stacked lines become one token, e.g. a column vector "(3, −2)";
- symbol-font private-use glyphs are mapped to Unicode (U+F02D → "−", U+F070 → "π", U+F0B4 → "×", ...);
- small glyphs raised above their line are powers ("^2"); recurring-decimal dots become U+0307 on the digit;
- the Marks cell is an integer, or per-line mark codes (M1, A2, B1) that are summed;
- sub-rows of a row whose Marks cell holds only method marks (M1) are method lines, not the answer.

Pure functions over a PDF path; no database, no LLM. See docs/notes/mark-scheme-parser.md.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf

# ---------------------------------------------------------------------------
# Glyph mapping
# ---------------------------------------------------------------------------

_SYMBOL = {
    0x20: " ", 0x21: "!", 0x22: "∀", 0x23: "#", 0x24: "∃", 0x25: "%", 0x26: "&", 0x27: "∋", 0x28: "(", 0x29: ")",
    0x2A: "∗", 0x2B: "+", 0x2C: ",", 0x2D: "−", 0x2E: ".", 0x2F: "/", 0x3A: ":", 0x3B: ";", 0x3C: "<", 0x3D: "=",
    0x3E: ">", 0x3F: "?", 0x40: "≅", 0x41: "Α", 0x42: "Β", 0x43: "Χ", 0x44: "Δ", 0x45: "Ε", 0x46: "Φ", 0x47: "Γ",
    0x48: "Η", 0x49: "Ι", 0x4A: "ϑ", 0x4B: "Κ", 0x4C: "Λ", 0x4D: "Μ", 0x4E: "Ν", 0x4F: "Ο", 0x50: "Π", 0x51: "Θ",
    0x52: "Ρ", 0x53: "Σ", 0x54: "Τ", 0x55: "Υ", 0x56: "ς", 0x57: "Ω", 0x58: "Ξ", 0x59: "Ψ", 0x5A: "Ζ", 0x5B: "[",
    0x5C: "∴", 0x5D: "]", 0x5E: "⊥", 0x5F: "_", 0x61: "α", 0x62: "β", 0x63: "χ", 0x64: "δ", 0x65: "ε", 0x66: "φ",
    0x67: "γ", 0x68: "η", 0x69: "ι", 0x6A: "ϕ", 0x6B: "κ", 0x6C: "λ", 0x6D: "μ", 0x6E: "ν", 0x6F: "ο", 0x70: "π",
    0x71: "θ", 0x72: "ρ", 0x73: "σ", 0x74: "τ", 0x75: "υ", 0x76: "ϖ", 0x77: "ω", 0x78: "ξ", 0x79: "ψ", 0x7A: "ζ",
    0x7B: "{", 0x7C: "|", 0x7D: "}", 0x7E: "∼", 0xA2: "′", 0xA3: "≤", 0xA4: "/", 0xA5: "∞", 0xAB: "↔", 0xAC: "←",
    0xAD: "↑", 0xAE: "→", 0xAF: "↓", 0xB0: "°", 0xB1: "±", 0xB2: "″", 0xB3: "≥", 0xB4: "×", 0xB5: "∝", 0xB6: "∂",
    0xB7: "•", 0xB8: "÷", 0xB9: "≠", 0xBA: "≡", 0xBB: "≈", 0xBC: "…", 0xC6: "∅", 0xC7: "∩", 0xC8: "∪", 0xC9: "⊃",
    0xCA: "⊇", 0xCB: "⊄", 0xCC: "⊂", 0xCD: "⊆", 0xCE: "∈", 0xCF: "∉", 0xD0: "∠", 0xD6: "√", 0xD7: "⋅", 0xDE: "⇒",
    0xE5: "∑", 0xF2: "∫",
}  # fmt: skip
for _code in range(0x30, 0x3A):
    _SYMBOL[_code] = chr(_code)

# Tall-bracket pieces (Symbol font): top, extension, bottom of ( ) [ ] { }.
_OPEN_PIECES = {0xE6: "(", 0xE7: "(", 0xE8: "(", 0xE9: "[", 0xEA: "[", 0xEB: "[", 0xEC: "{", 0xED: "{", 0xEE: "{"}
_CLOSE_PIECES = {0xF6: ")", 0xF7: ")", 0xF8: ")", 0xF9: "]", 0xFA: "]", 0xFB: "]", 0xFC: "}", 0xFD: "}", 0xFE: "}"}
_CLOSING = {"(": ")", "[": "]", "{": "}"}
RECURRING_DOT = "̇"
UNMAPPED = "�"
MINUS = "−"


def map_glyph(char: str, font: str) -> tuple[str, str]:
    """(text, kind) for one PDF glyph. kind: "char", "open"/"close" (tall-bracket piece), "dot" (recurring dot)."""
    code = ord(char)
    if 0xF000 <= code <= 0xF0FF:  # symbol fonts expose their 8-bit code in the private-use area
        low = code - 0xF000
        name = font.lower()
        if "extra" in name:  # MT Extra: dot accents over recurring digits
            return ("", "dot") if low in (0x26, 0x5F) else (UNMAPPED, "char")
        if "symbol" in name:
            if low in _OPEN_PIECES:
                return _OPEN_PIECES[low], "open"
            if low in _CLOSE_PIECES:
                return _CLOSE_PIECES[low], "close"
            if low in _SYMBOL:
                return _SYMBOL[low], "char"
        if 0x20 <= low < 0x7F and "symbol" not in name:
            return chr(low), "char"
        return UNMAPPED, "char"
    if 0xE000 <= code <= 0xF8FF:
        return UNMAPPED, "char"
    if char == "–":  # the mark schemes print minus signs as en dashes
        return MINUS, "char"
    return char, "char"


# ---------------------------------------------------------------------------
# Layout primitives
# ---------------------------------------------------------------------------


@dataclass
class Item:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    kind: str = "char"  # char | space | token | open | close | dot

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass(frozen=True)
class Rule:
    x0: float
    y0: float
    x1: float
    y1: float
    stroked: bool

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def page_items(page: pymupdf.Page) -> list[Item]:
    items: list[Item] = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    text, kind = map_glyph(ch["c"], span["font"])
                    x0, y0, x1, y1 = ch["bbox"]
                    if kind == "char" and not text.strip():
                        kind = "space"
                    items.append(Item(text, x0, y0, x1, y1, span["size"], kind))
    return items


def page_rules(page: pymupdf.Page) -> list[Rule]:
    """Thin drawn lines/rectangles: table rules and fraction bars."""
    rules: list[Rule] = []
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if min(r.width, r.height) <= 1.5 and max(r.width, r.height) >= 2:
            rules.append(Rule(r.x0, r.y0, r.x1, r.y1, drawing.get("type") == "s"))
    return rules


Box = tuple[float, float, float, float]


def page_graphics(page: pymupdf.Page) -> list[Box]:
    """Boxes of drawn shapes that are not thin rules, and of images: diagrams, graphs and sketches."""
    boxes: list[Box] = []
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if min(r.width, r.height) > 6:
            boxes.append((r.x0, r.y0, r.x1, r.y1))
    boxes.extend(tuple(info["bbox"]) for info in page.get_image_info())  # type: ignore[misc]
    return boxes


# ---------------------------------------------------------------------------
# Cell rendering
# ---------------------------------------------------------------------------

_SIMPLE_TERM = re.compile(rf"^{MINUS}?[A-Za-z0-9.π{RECURRING_DOT}]+$")


def _wrap(text: str) -> str:
    return text if _SIMPLE_TERM.match(text) else f"({text})"


def _fraction_tokens(items: list[Item], bars: Sequence[Rule]) -> list[Item]:
    """Replace numerator / bar / denominator groups with one inline token each (narrowest bar first)."""
    for bar in sorted(bars, key=lambda b: b.width):
        y = (bar.y0 + bar.y1) / 2

        def over(it: Item, bar: Rule = bar) -> bool:
            return bar.x0 - 1.5 <= it.cx <= bar.x1 + 1.5 and it.kind != "space"

        numerator = [it for it in items if over(it) and y - 4.5 <= it.y1 <= y + 1.5 and it.cy < y]
        denominator = [it for it in items if over(it) and y - 1.5 <= it.y0 <= y + 4.5 and it.cy > y]
        if not numerator or not denominator:
            continue
        num, den = render_inline(numerator), render_inline(denominator)
        if not num or not den:
            continue
        taken = {id(it) for it in numerator + denominator}
        size = max(it.size for it in numerator + denominator)
        token = Item(f"{_wrap(num)}/{_wrap(den)}", bar.x0, y - size / 2, bar.x1, y + size / 2, size, "token")
        items = [it for it in items if id(it) not in taken] + [token]
    return items


def _bracket_tokens(items: list[Item]) -> list[Item]:
    """Tall bracket pairs enclosing stacked content → "(a, b)" (a column vector) or "(a)" for one line."""
    opens = [it for it in items if it.kind == "open"]
    closes = [it for it in items if it.kind == "close"]
    used: set[int] = set()
    for opener in sorted(opens, key=lambda it: it.x0):
        if id(opener) in used:
            continue
        column = [it for it in opens if abs(it.cx - opener.cx) < 2 and it.text == opener.text and id(it) not in used]
        top, bottom = min(it.y0 for it in column), max(it.y1 for it in column)
        match = [
            it
            for it in closes
            if it.text == _CLOSING[opener.text]
            and it.x0 > opener.x1
            and id(it) not in used
            and top - 4 < it.cy < bottom + 4
        ]
        if not match:
            continue
        nearest_x = min(it.cx for it in match)
        closers = [it for it in match if abs(it.cx - nearest_x) < 2]
        inside = [
            it
            for it in items
            if it.kind in ("char", "token", "dot", "space")
            and opener.x1 - 0.5 <= it.cx <= min(c.x0 for c in closers) + 0.5
            and top - 1 <= it.cy <= bottom + 1
        ]
        used.update(id(it) for it in column + closers)
        lines = [line for line in render_lines(inside) if line]
        taken = {id(it) for it in inside + column + closers}
        size = max((it.size for it in inside), default=opener.size)
        text = opener.text + ", ".join(lines) + _CLOSING[opener.text]
        token = Item(
            text,
            opener.x0,
            (top + bottom) / 2 - size / 2,
            max(c.x1 for c in closers),
            (top + bottom) / 2 + size / 2,
            size,
            "token",
        )
        items = [it for it in items if id(it) not in taken] + [token]
    # Unpaired pieces: keep one bracket per vertical column of pieces.
    leftovers = [it for it in items if it.kind in ("open", "close")]
    keep: list[Item] = []
    for piece in sorted(leftovers, key=lambda it: it.cy):
        if not any(abs(k.cx - piece.cx) < 2 and k.text == piece.text for k in keep):
            keep.append(Item(piece.text, piece.x0, piece.y0, piece.x1, piece.y1, piece.size, "char"))
    return [it for it in items if it.kind not in ("open", "close")] + keep


def render_lines(items: Sequence[Item]) -> list[str]:
    """Cluster items into visual lines (top to bottom) and render each line left to right."""
    body = [it for it in items if it.kind in ("char", "token")]
    if not body:
        return []
    median = statistics.median(it.size for it in body)
    normal = [it for it in body if it.size >= 0.8 * median]
    small = [it for it in body if it.size < 0.8 * median]
    lines: list[list[Item]] = []
    for it in sorted(normal, key=lambda it: it.cy):
        if lines and it.cy - statistics.fmean(m.cy for m in lines[-1]) <= 0.5 * median:
            lines[-1].append(it)
        else:
            lines.append([it])
    if not lines:
        lines = [small]
        small = []
    centres = [statistics.fmean(m.cy for m in line) for line in lines]
    extras: list[list[tuple[Item, str]]] = [[] for _ in lines]
    for it in small:
        i = min(range(len(lines)), key=lambda k: abs(centres[k] - it.cy))
        role = "sup" if it.cy < centres[i] - 0.12 * median else "sub" if it.cy > centres[i] + 0.12 * median else "char"
        extras[i].append((it, role))
    for it in items:
        if it.kind == "dot":
            i = min(range(len(lines)), key=lambda k: abs(centres[k] - it.cy))
            extras[i].append((it, "dot"))
        elif it.kind == "space":
            i = min(range(len(lines)), key=lambda k: abs(centres[k] - it.cy))
            if abs(centres[i] - it.cy) <= 0.5 * median:
                extras[i].append((it, "space"))
    return [_render_line(line, extra, median) for line, extra in zip(lines, extras, strict=True)]


def _render_line(line: list[Item], extras: list[tuple[Item, str]], median: float) -> str:
    entries = [(it, "char") for it in line] + [e for e in extras if e[1] != "dot"]
    entries.sort(key=lambda e: (e[0].x0, e[0].cx))
    dots = [e[0] for e in extras if e[1] == "dot"]
    dotted: set[int] = set()
    for dot in dots:  # a recurring dot belongs to the digit it sits over
        digits = [it for it, role in entries if role == "char" and it.text.isdigit()]
        if digits:
            dotted.add(id(min(digits, key=lambda it: abs(it.cx - dot.cx))))
    out: list[str] = []
    prev: Item | None = None
    pending_space = False
    script_role = ""
    for it, role in entries:
        if role == "space":
            pending_space = prev is not None
            continue
        if prev is not None and (pending_space or it.x0 - prev.x1 > 0.25 * median) and role == "char":
            out.append(" ")
        pending_space = False
        if role in ("sup", "sub"):
            marker = "^" if role == "sup" else "_"
            if script_role != role:
                out.append(marker)
            out.append(it.text)
        else:
            out.append(it.text + (RECURRING_DOT if id(it) in dotted else ""))
        script_role = role if role in ("sup", "sub") else ""
        prev = it
    return re.sub(r" {2,}", " ", "".join(out)).strip()


def render_inline(items: Sequence[Item]) -> str:
    return " ".join(line for line in render_lines(_bracket_tokens(list(items))) if line)


def render_cell(items: Sequence[Item], bars: Sequence[Rule]) -> str:
    tokens = _bracket_tokens(_fraction_tokens(list(items), bars))
    return "\n".join(line for line in render_lines(tokens) if line)


# ---------------------------------------------------------------------------
# Table structure
# ---------------------------------------------------------------------------

COLUMNS = ("question", "answer", "marks", "partial")


@dataclass(frozen=True)
class TableLayout:
    bounds: dict[str, tuple[float, float]]  # column -> (x0, x1)
    top: float  # below the header row
    bottom: float


def _header_words(page: pymupdf.Page) -> dict[str, tuple[float, float, float, float]] | None:
    words = page.get_text("words")
    for q in (w for w in words if w[4] == "Question"):
        same_line = [w for w in words if abs(w[1] - q[1]) < 3 and w[0] > q[0]]
        found = {"question": q[:4]}
        for name, label in (("answer", "Answer"), ("marks", "Marks"), ("partial", "Partial")):
            match = [w for w in same_line if w[4] == label]
            if match:
                found[name] = min(match, key=lambda w: w[0])[:4]
        if {"answer", "marks", "partial"} <= found.keys() and (
            found["question"][0] < found["answer"][0] < found["marks"][0] < found["partial"][0]
        ):
            return found
    return None


def find_layout(page: pymupdf.Page, rules: Sequence[Rule]) -> TableLayout | None:
    header = _header_words(page)
    if header is None:
        return None
    header_bottom = max(h[3] for h in header.values())
    verticals = [r for r in rules if r.width <= 1.5 and r.height > 5 and r.y1 > header_bottom]
    # Total drawn length per x: column rules run the whole table; a rule inside a cell (e.g. a small table in the
    # Answer column) is short, so between two header words the longest rule is the column boundary.
    length: dict[float, float] = {}
    for r in verticals:
        x = round((r.x0 + r.x1) / 2, 1)
        length[x] = length.get(x, 0.0) + r.height
    order = [header[c] for c in COLUMNS]
    edges: list[float] = []
    for i, word in enumerate(order):
        left_limit = order[i - 1][2] if i else 0.0
        candidates = [x for x in length if left_limit - 0.5 <= x <= word[0] + 0.5]
        if candidates:
            edges.append(max(candidates, key=lambda x: (length[x], x)))
        else:
            edges.append((left_limit + word[0]) / 2 if i else word[0] - 8)
    right = [x for x in length if x >= order[-1][2]]
    edges.append(max(right, key=lambda x: (length[x], -x)) if right else page.rect.width - 40)
    bounds = {name: (edges[i], edges[i + 1]) for i, name in enumerate(COLUMNS)}
    in_table = [r.y1 for r in verticals if edges[0] - 1 <= (r.x0 + r.x1) / 2 <= edges[-1] + 1]
    bottom = max(in_table) if in_table else page.rect.height - 50
    return TableLayout(bounds, header_bottom + 1, bottom)


_ROMAN = r"(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)"
# 7, 7(a), 7(b)(ii), and the occasional fourth level 2(a)(vi)(a) (same grammar as past_papers.normalise_ref).
_FULL_REF = re.compile(rf"^(\d{{1,2}})((?:\([a-z]\))?(?:\({_ROMAN}\)(?:\([a-z]\))?)?)$")
_LETTER_ONLY = re.compile(r"^\(([a-z])\)$")
_ROMAN_ONLY = re.compile(rf"^\(({_ROMAN})\)$")


def normalise_ref(ref: str) -> str | None:
    compact = re.sub(r"\s+", "", ref).lower().removeprefix("q")
    return compact if _FULL_REF.match(compact) else None


def resolve_ref(text: str, previous: str | None) -> str | None:
    """A Question-column label as a full ref; "(b)" / "(ii)" continue the previous ref's question / part."""
    compact = re.sub(r"\s+", "", text).lower()
    if full := normalise_ref(compact):
        return full
    if previous is None:
        return None
    prev = _FULL_REF.match(previous)
    if prev is None:
        return None
    if _LETTER_ONLY.match(compact):
        return prev.group(1) + compact
    if _ROMAN_ONLY.match(compact):
        letter = re.match(r"\([a-z]\)", prev.group(2))
        return prev.group(1) + (letter.group(0) if letter else "") + compact
    return None


@dataclass
class SubRow:
    answer: str
    marks_text: str
    diagram: bool = False  # the answer cell holds a drawn shape or image (the text is not the whole answer)


@dataclass
class MarkSchemeRow:
    ref: str
    marks: int | None
    answer: str  # final answer lines as printed (method-only lines excluded)
    method: str  # answer-column lines credited only with method marks
    partial_marks: str
    marks_text: str
    pages: list[int]
    accept_ranges: list[tuple[str, str]] = field(default_factory=list)
    accuracy_hints: list[str] = field(default_factory=list)
    notation: list[str] = field(default_factory=list)

    @property
    def guidance(self) -> str:
        """Marking guidance for storage: method lines plus partial marks."""
        return "\n".join(part for part in (self.method, self.partial_marks) if part)


@dataclass
class MarkSchemeTable:
    rows: list[MarkSchemeRow]
    pages: list[int]
    issues: list[str] = field(default_factory=list)
    unmapped_glyphs: int = 0

    def by_ref(self) -> dict[str, MarkSchemeRow]:
        return {row.ref: row for row in self.rows}

    @property
    def total_marks(self) -> int:
        return sum(row.marks or 0 for row in self.rows)

    def empty_answers(self) -> list[str]:
        return [row.ref for row in self.rows if not row.answer]


@dataclass
class _Segment:
    ref: str | None
    page: int
    y0: float
    y1: float


def _question_labels(items: Sequence[Item], layout: TableLayout) -> list[tuple[str, float]]:
    x0, x1 = layout.bounds["question"]
    cell = [it for it in items if x0 <= it.cx < x1 and layout.top <= it.cy <= layout.bottom and it.kind != "space"]
    labels: list[tuple[str, float]] = []
    for line in _cluster_lines(cell):
        text = "".join(it.text for it in sorted(line, key=lambda it: it.x0))
        labels.append((text, min(it.y0 for it in line)))
    return labels


def _cluster_lines(items: Sequence[Item]) -> list[list[Item]]:
    lines: list[list[Item]] = []
    for it in sorted(items, key=lambda it: it.cy):
        if lines and it.cy - statistics.fmean(m.cy for m in lines[-1]) <= 0.5 * it.size:
            lines[-1].append(it)
        else:
            lines.append([it])
    return lines


def _row_rules(rules: Sequence[Rule], layout: TableLayout, column: str) -> list[float]:
    x0, x1 = layout.bounds[column]
    width = x1 - x0
    return sorted(
        (r.y0 + r.y1) / 2
        for r in rules
        if r.height <= 1.5 and r.width >= 0.8 * width and r.x0 <= x0 + 2 and r.x1 >= x1 - 2
    )


_INT = re.compile(r"^\d{1,2}$")
_MARK_CODE = re.compile(r"^[MAB](\d)[A-Za-z]{0,4}$")  # M1, A2, B1, M1dep, B2FT
_METHOD_ONLY = re.compile(r"^(?:M\d[A-Za-z]{0,4}\s*)+$")


def parse_marks(marks_text: str) -> int | None:
    """Integer total, or the sum of mark codes (M1, A2, B2FT, M1dep) when the column lists them per line."""
    tokens = marks_text.replace("\n", " ").split()
    integers = [int(t) for t in tokens if _INT.match(t)]
    if integers:
        return sum(integers)
    codes = [int(m.group(1)) for t in tokens if (m := _MARK_CODE.match(t))]
    return sum(codes) if codes else None


def parse_pdf(path: Path | str) -> MarkSchemeTable | None:
    """Parse a mark-scheme PDF. None when it has no Question/Answer/Marks/Partial Marks table (e.g. prose schemes)."""
    with pymupdf.open(path) as doc:
        return parse_document(doc)


def parse_document(doc: pymupdf.Document) -> MarkSchemeTable | None:
    segments: list[tuple[_Segment, list[SubRow], str]] = []
    issues: list[str] = []
    pages: list[int] = []
    unmapped = 0
    previous_ref: str | None = None
    for page in doc:
        rules = page_rules(page)
        layout = find_layout(page, rules)
        if layout is None:
            continue
        number = page.number + 1
        pages.append(number)
        items = [it for it in page_items(page) if layout.top <= it.cy <= layout.bottom]
        graphics = page_graphics(page)
        unmapped += sum(it.text == UNMAPPED for it in items)
        question_rules = _row_rules(rules, layout, "question")
        answer_rules = _row_rules(rules, layout, "answer")
        starts: list[tuple[str, float]] = []
        for text, top in _question_labels(items, layout):
            ref = resolve_ref(text, previous_ref)
            if ref is None:
                issues.append(f"p{number}:unreadable_question_label")
                continue
            above = [y for y in question_rules if y <= top + 1]
            starts.append((ref, max(above) if above else top - 2))
            previous_ref = ref
        bounds = [layout.top, *(y for _, y in starts), layout.bottom]
        refs: list[str | None] = [None, *(ref for ref, _ in starts)]
        for i, ref in enumerate(refs):
            y0, y1 = bounds[i], bounds[i + 1]
            if y1 - y0 < 1:
                continue
            seg = _Segment(ref, number, y0, y1)
            subs, partial = _sub_rows(items, rules, graphics, layout, seg, answer_rules)
            if ref is None and not partial and not any(s.answer or s.marks_text for s in subs):
                continue
            segments.append((seg, subs, partial))
    if not pages:
        return None
    rows = _assemble(segments, issues)
    table = MarkSchemeTable(rows, pages, issues, unmapped)
    if unmapped:
        table.issues.append(f"unmapped_glyphs:{unmapped}")
    return table


def _cell_items(items: Sequence[Item], layout: TableLayout, column: str, y0: float, y1: float) -> list[Item]:
    x0, x1 = layout.bounds[column]
    return [it for it in items if x0 <= it.cx < x1 and y0 <= it.cy < y1]


def _cell_bars(rules: Sequence[Rule], layout: TableLayout, column: str, y0: float, y1: float) -> list[Rule]:
    x0, x1 = layout.bounds[column]
    return [
        r
        for r in rules
        if r.height <= 1.5 and r.width >= 2.5 and r.x0 >= x0 + 1 and r.x1 <= x1 - 1 and y0 <= (r.y0 + r.y1) / 2 <= y1
    ]


def _sub_rows(
    items: Sequence[Item],
    rules: Sequence[Rule],
    graphics: Sequence[Box],
    layout: TableLayout,
    seg: _Segment,
    answer_rules: Sequence[float],
) -> tuple[list[SubRow], str]:
    """(answer/marks sub-rows split at rules across the Answer column, partial-marks text for the whole segment)."""
    cuts = [seg.y0, *(y for y in answer_rules if seg.y0 + 2 < y < seg.y1 - 2), seg.y1]
    ax0, ax1 = layout.bounds["answer"]
    subs: list[SubRow] = []
    for a, b in zip(cuts, cuts[1:], strict=False):
        answer = render_cell(_cell_items(items, layout, "answer", a, b), _cell_bars(rules, layout, "answer", a, b))
        marks = render_cell(_cell_items(items, layout, "marks", a, b), [])
        diagram = any(
            ax0 <= (gx0 + gx1) / 2 <= ax1 and a <= (gy0 + gy1) / 2 <= b and gx1 - gx0 < ax1 - ax0 - 2
            for gx0, gy0, gx1, gy1 in graphics
        )
        subs.append(SubRow(answer, marks, diagram))
    partial = render_cell(
        _cell_items(items, layout, "partial", seg.y0, seg.y1), _cell_bars(rules, layout, "partial", seg.y0, seg.y1)
    )
    return subs, partial


def _assemble(segments: Sequence[tuple[_Segment, list[SubRow], str]], issues: list[str]) -> list[MarkSchemeRow]:
    collected: dict[str, dict[str, object]] = {}
    order: list[str] = []
    current: str | None = None
    for seg, subs, partial in segments:
        ref = seg.ref or current
        if ref is None:
            issues.append(f"p{seg.page}:content_before_first_ref")
            continue
        if seg.ref is not None and seg.ref in collected and seg.ref != current:
            issues.append(f"duplicate_ref:{seg.ref}")
        current = ref
        if ref not in collected:
            collected[ref] = {"subs": [], "partial": [], "pages": []}
            order.append(ref)
        entry = collected[ref]
        entry["subs"].extend(sub for sub in subs if sub.answer or sub.marks_text)  # type: ignore[attr-defined]
        if partial:
            entry["partial"].append(partial)  # type: ignore[attr-defined]
        if seg.page not in entry["pages"]:  # type: ignore[operator]
            entry["pages"].append(seg.page)  # type: ignore[attr-defined]
    rows: list[MarkSchemeRow] = []
    for ref in order:
        entry = collected[ref]
        subs: list[SubRow] = entry["subs"]  # type: ignore[assignment]
        marks_text = "\n".join(s.marks_text for s in subs if s.marks_text)
        final = [s for s in subs if not _METHOD_ONLY.match(s.marks_text.replace("\n", " ").strip())]
        method = [s for s in subs if s not in final]
        if not any(s.answer for s in final):  # only method sub-rows: keep everything as the answer
            final, method = subs, []
        answer = "\n".join(s.answer for s in final if s.answer)
        row = MarkSchemeRow(
            ref=ref,
            marks=parse_marks(marks_text),
            answer=answer,
            method="\n".join(s.answer for s in method if s.answer),
            partial_marks="\n".join(entry["partial"]),  # type: ignore[arg-type]
            marks_text=marks_text,
            pages=list(entry["pages"]),  # type: ignore[call-overload]
        )
        row.accept_ranges = accept_ranges(answer)
        row.accuracy_hints = accuracy_hints(answer)
        row.notation = notation_flags(answer)
        if any(s.diagram for s in final):
            row.notation.append("diagram")
        if row.marks is None:
            issues.append(f"marks_unparsed:{ref}")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Derived fields
# ---------------------------------------------------------------------------

_NUM = r"-?\d+(?:\.\d+)?"
_RANGE = re.compile(rf"({_NUM})\s*(?:to)\s*({_NUM})")
_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")


def plain(text: str) -> str:
    """ASCII-friendly form for numeric work: minus signs, recurring dots and thousands spaces normalised."""
    out = text.replace(MINUS, "-").replace("–", "-").replace(RECURRING_DOT, "").replace("…", "")
    return re.sub(r"(?<![\d.])(\d{1,3}) (\d{3})(?![\d.])", r"\1\2", out)


def accept_ranges(answer: str) -> list[tuple[str, str]]:
    ranges: list[tuple[str, str]] = []
    for lo, hi in _RANGE.findall(plain(answer)):
        try:
            a, b = Decimal(lo), Decimal(hi)
        except InvalidOperation:
            continue
        ranges.append((lo, hi) if a <= b else (hi, lo))
    return ranges


_HINTS = (
    ("cao", re.compile(r"\bcao\b")),
    ("oe", re.compile(r"\boe\b")),
    ("isw", re.compile(r"\bisw\b")),
    ("nfww", re.compile(r"\bnfww\b")),
    ("ft", re.compile(r"\bft\b")),
    ("soi", re.compile(r"\bsoi\b")),
    ("dep", re.compile(r"\bdep\b")),
    ("final_answer", re.compile(r"final answer", re.IGNORECASE)),
    ("exact", re.compile(r"\bexact\b", re.IGNORECASE)),
)
_PLACES = re.compile(r"(?:correct\s+to\s+|to\s+)?(\d)\s*(dp|sf|decimal places?|significant figures?)", re.IGNORECASE)


def accuracy_hints(answer: str) -> list[str]:
    hints = [name for name, pattern in _HINTS if pattern.search(answer)]
    for n, unit in _PLACES.findall(answer):
        hints.append(f"{'dp' if unit.lower().startswith(('dp', 'decimal')) else 'sf'}:{n}")
    return hints


def notation_flags(answer: str) -> list[str]:
    flags = []
    if re.search(r"[\w)]\s*/\s*[\w(]", answer):
        flags.append("fraction")
    if RECURRING_DOT in answer:
        flags.append("recurring")
    if "^" in answer:
        flags.append("power")
    if "√" in answer:
        flags.append("root")
    if "π" in answer:
        flags.append("pi")
    if _RANGE.search(plain(answer)):
        flags.append("range")
    if "\n" in answer:
        flags.append("multi_line")
    return flags


def numbers(text: str) -> set[str]:
    """Distinct numeric values in text (normalised decimals), for comparing answers."""
    cleaned = plain(text).replace(", ", " ").replace(",", "")
    return {format(Decimal(n).normalize(), "f") for n in _NUMBER_TOKEN.findall(cleaned)}


def looks_tabular(table: MarkSchemeTable | None, *, min_rows: int = 5) -> bool:
    """A parse is usable only if it found enough rows and nearly all of them have readable marks."""
    if table is None or len(table.rows) < min_rows:
        return False
    return sum(row.marks is not None for row in table.rows) >= 0.9 * len(table.rows)
