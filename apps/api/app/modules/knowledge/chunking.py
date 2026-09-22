"""Structure-aware chunking of extracted pages (ARCHITECTURE §9.2). Pure functions: pages in, chunk drafts out.

Rules:
- Blocks start at Markdown headings; a block keeps its heading path (e.g. "Chapter 5 > 5.4 > Example 3").
- Worked examples and exercises start their own chunk and are never merged with prose, so an example stays whole.
- Small neighbouring prose blocks are packed up to TARGET_CHARS; a block over MAX_CHARS is split at paragraphs.
- "Answers to ..." sections are skipped: retrieval must not hand out exercise answers.
"""

from __future__ import annotations

import bisect
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

TARGET_CHARS = 1800
MAX_CHARS = 3000
MIN_CHARS = 300

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
_KIND_RULES = (
    (re.compile(r"^(worked\s+)?examples?\b", re.IGNORECASE), "worked_example"),
    (re.compile(r"^(exercise|examination questions)\b", re.IGNORECASE), "exercise"),
    (re.compile(r"^key\s+terms?\b", re.IGNORECASE), "definition"),
)
_STANDALONE_KINDS = frozenset({"worked_example", "exercise"})
_ANSWERS = re.compile(r"^answers?\b", re.IGNORECASE)
_CHAPTER = re.compile(r"^chapter\b", re.IGNORECASE)


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class ChunkDraft:
    content: str
    page_start: int
    page_end: int
    heading_path: str | None
    content_kind: str


@dataclass
class _Block:
    lines: list[str]
    page_start: int
    page_end: int
    heading_path: str | None
    kind: str
    has_heading: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def has_body(self) -> bool:
        return any(line.strip() for line in self.lines[1 if self.has_heading else 0 :])


def page_offset(labels: Sequence[tuple[int, str | None]]) -> int | None:
    """Most common (PDF page - printed page) over pages with a numeric printed label; None if none."""
    diffs = Counter(page - int(label) for page, label in labels if label and label.strip().isdigit())
    return diffs.most_common(1)[0][0] if diffs else None


_EDGE_NUMBER = re.compile(r"(?<![\d.,/])(\d{1,4})(?![\d.,/%])")
EDGE_LINES = 3


def detect_printed_labels(pages: Sequence[tuple[int, str]], *, edge_lines: int = EDGE_LINES) -> dict[int, str]:
    """Printed page numbers of a text-layer book, which the text layer does not mark as such.

    Candidates are standalone numbers in each page's first and last ``edge_lines`` lines. The book's offset
    (PDF page - printed page) is the one most candidates agree on; a page is labelled only where one of its own
    candidates fits that offset, so a figure number, a year or a question number at the edge of a page is ignored.
    Returns {} when too few pages agree to trust an offset.
    """
    candidates: dict[int, set[int]] = {}
    for page, text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        edge = lines[:edge_lines] + lines[-edge_lines:]
        candidates[page] = {int(n) for line in edge for n in _EDGE_NUMBER.findall(line) if 0 < int(n) <= page}
    votes = Counter(page - n for page, found in candidates.items() for n in found)
    if not votes:
        return {}
    offset, count = votes.most_common(1)[0]
    if count < max(3, len(pages) // 10):
        return {}
    return {page: str(page - offset) for page, found in candidates.items() if page - offset in found}


def printed_page_map(labels: Sequence[tuple[int, str | None]]) -> dict[int, int]:
    """PDF page -> printed page. A page's own numeric label wins; otherwise the offset of the nearest labelled page
    (scans can gain or lose pages part-way through, so one global offset is not enough)."""
    known = sorted((page, page - int(label)) for page, label in labels if label and label.strip().isdigit())
    if not known:
        return {}
    pages = [page for page, _ in known]
    mapping: dict[int, int] = {}
    for page, _ in labels:
        i = bisect.bisect_left(pages, page)
        neighbours = [known[j] for j in (i - 1, i) if 0 <= j < len(known)]
        _, offset = min(neighbours, key=lambda item: abs(item[0] - page))
        if page - offset >= 1:  # front matter before printed page 1 has no printed number
            mapping[page] = page - offset
    return mapping


def _kind_for(titles: Sequence[str], default_kind: str) -> str:
    for title in reversed(titles):  # nearest heading first, then its ancestors
        for pattern, kind in _KIND_RULES:
            if pattern.match(title):
                return kind
    return default_kind


def split_blocks(pages: Sequence[PageText], default_kind: str) -> tuple[list[_Block], set[int]]:
    """Heading-delimited blocks in reading order, plus the page numbers skipped as answer sections."""
    path: dict[int, str] = {}
    blocks: list[_Block] = []
    skipped: set[int] = set()
    current: _Block | None = None
    in_answers = False
    for page in sorted(pages, key=lambda p: p.page_number):
        for line in page.text.splitlines():
            heading = _HEADING.match(line)
            if heading:
                level, title = len(heading.group(1)), heading.group(2).strip()
                if _ANSWERS.match(title):
                    in_answers = True
                elif in_answers and level == 1 and _CHAPTER.match(title) and "answer" not in title.lower():
                    in_answers = False
                path = {lvl: t for lvl, t in path.items() if lvl < level}
                path[level] = title
                titles = [path[lvl] for lvl in sorted(path)]
                current = _Block([line], page.page_number, page.page_number, " > ".join(titles), "", True)
                current.kind = _kind_for(titles, default_kind)
                if in_answers:
                    skipped.add(page.page_number)
                else:
                    blocks.append(current)
                continue
            if in_answers:
                skipped.add(page.page_number)
                continue
            # Text with no heading above it (a text-layer book has no Markdown headings at all) starts a new block
            # on each page, so every chunk keeps the page it came from and can be tagged by printed page. A block
            # under a heading still runs on across pages, as before.
            if current is None or (not current.has_heading and current.page_start != page.page_number):
                current = _Block([], page.page_number, page.page_number, None, default_kind)
                blocks.append(current)
            current.lines.append(line)
            current.page_end = page.page_number
    return blocks, skipped


def _split_long(text: str, limit: int) -> list[str]:
    pieces: list[str] = []
    buffer = ""
    for paragraph in re.split(r"\n\s*\n", text):
        units = [paragraph] if len(paragraph) <= MAX_CHARS else paragraph.splitlines()
        for unit in units:
            while len(unit) > MAX_CHARS:  # a single enormous line: hard split
                pieces.append(unit[:MAX_CHARS])
                unit = unit[MAX_CHARS:]
            if buffer and len(buffer) + len(unit) + 2 > limit:
                pieces.append(buffer)
                buffer = ""
            buffer = f"{buffer}\n\n{unit}" if buffer else unit
    if buffer.strip():
        pieces.append(buffer)
    return [p.strip() for p in pieces if p.strip()]


def pack_blocks(blocks: Sequence[_Block]) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    buffer: list[_Block] = []

    def flush() -> None:
        texts = [b for b in buffer if b.text]
        if texts:
            kinds = Counter()
            for b in texts:
                kinds[b.kind] += len(b.text)
            drafts.append(
                ChunkDraft(
                    content="\n\n".join(b.text for b in texts),
                    page_start=texts[0].page_start,
                    page_end=texts[-1].page_end,
                    # The first block with body text names the chunk ("Chapter 2 > 2.1 Fractions", not "Chapter 2").
                    heading_path=next((b.heading_path for b in texts if b.has_body), texts[0].heading_path),
                    content_kind=kinds.most_common(1)[0][0],
                )
            )
        buffer.clear()

    for block in blocks:
        text = block.text
        if not text:
            continue
        if len(text) > MAX_CHARS:
            flush()
            drafts.extend(
                ChunkDraft(piece, block.page_start, block.page_end, block.heading_path, block.kind)
                for piece in _split_long(text, TARGET_CHARS)
            )
            continue
        size = sum(len(b.text) for b in buffer)
        kind_change = bool(buffer) and (block.kind in _STANDALONE_KINDS or buffer[-1].kind in _STANDALONE_KINDS)
        kind_change = kind_change and block.kind != buffer[-1].kind
        if buffer and (kind_change or (size + len(text) > TARGET_CHARS and size >= MIN_CHARS)):
            flush()
        buffer.append(block)
    flush()
    return drafts


def chunk_pages(pages: Sequence[PageText], default_kind: str) -> tuple[list[ChunkDraft], set[int]]:
    blocks, skipped = split_blocks(pages, default_kind)
    return pack_blocks(blocks), skipped


def section_for_page[T](printed_page: int, starts: Sequence[tuple[int, T]]) -> T | None:
    """The section whose start page is the last one at or before printed_page (starts sorted by page)."""
    index = bisect.bisect_right([page for page, _ in starts], printed_page) - 1
    return starts[index][1] if index >= 0 else None


def sections_for_span[T](first: int, last: int, starts: Sequence[tuple[int, T]]) -> list[T]:
    """Every section a chunk spanning printed pages first..last belongs to: the one it opens in, and any that start
    inside it. A long book section with no sub-headings is chunked as one heading, so its chunks all carry the
    section's first page; tagging by that page alone gave Group I and Group VII (Chemistry 13.2) to the Periodic
    Table topic before them (22 Sep 2026)."""
    out: list[T] = []
    opening = section_for_page(first, starts)
    if opening is not None:
        out.append(opening)
    for page, section in starts:
        if first < page <= last and section not in out:
            out.append(section)
    return out
