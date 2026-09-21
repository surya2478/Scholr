"""Vision OCR for scanned PDF pages (textbooks without a text layer).

Options are chosen per source in its manifest and screened with app.jobs.ocr_eval:
- output "markdown" asks for the transcription as plain text. JSON output makes models escape every backslash, and
  low-cost models get that wrong for LaTeX (\\times arrives as a TAB + "imes").
- dpi / bands render the page larger, optionally as overlapping horizontal bands, so small glyphs (root indices,
  division signs) are legible to the model.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pymupdf
from pydantic import BaseModel

from app.llm.gateway import CallContext, ImageInput, LLMGateway

OCR_PROMPT = "page_ocr"
BAND_OVERLAP = 0.05  # fraction of page height shared by neighbouring bands
OutputFormat = Literal["json", "markdown"]
_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", re.DOTALL)


class OcrPage(BaseModel):
    printed_page_label: str | None = None
    running_header: str | None = None
    markdown: str
    has_figures: bool = False
    has_handwriting: bool = False
    legibility: Literal["good", "fair", "poor"] = "good"


@dataclass(frozen=True)
class OcrOptions:
    role: str = "page_ocr"
    prompt: str = OCR_PROMPT
    output: OutputFormat = "json"
    dpi: int = 150
    bands: int = 1
    models: tuple[str, ...] | None = None  # override the role's models (screening only)


@dataclass(frozen=True)
class OcrResult:
    markdown: str
    printed_page_label: str | None
    meta: dict[str, Any]
    model: str
    prompt_name: str
    prompt_version: str
    cost_usd: float
    output_tokens: int


def page_count(pdf_path: Path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return int(doc.page_count)


def has_text_layer(pdf_path: Path, sample_pages: int = 5, min_chars: int = 200) -> bool:
    with pymupdf.open(pdf_path) as doc:
        total = sum(len(doc[i].get_text()) for i in range(min(sample_pages, doc.page_count)))
    return total >= min_chars


def render_page_png(pdf_path: Path, page_index: int, *, dpi: int = 150, band: int = 0, bands: int = 1) -> bytes:
    with pymupdf.open(pdf_path) as doc:
        page = doc[page_index]
        clip = None
        if bands > 1:
            rect = page.rect
            top = max(0.0, (band / bands - BAND_OVERLAP) * rect.height)
            bottom = min(rect.height, ((band + 1) / bands + BAND_OVERLAP) * rect.height)
            clip = pymupdf.Rect(rect.x0, rect.y0 + top, rect.x1, rect.y0 + bottom)
        return bytes(page.get_pixmap(dpi=dpi, clip=clip).tobytes("png"))


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lower()


def merge_bands(parts: Sequence[str], window: int = 8) -> str:
    """Join band transcriptions top to bottom, dropping lines repeated in the overlap between bands."""
    merged: list[str] = []
    for text in parts:
        lines = text.strip("\n").splitlines()
        tail = [_norm(line) for line in merged if _norm(line)][-window:]
        head = [i for i, line in enumerate(lines) if _norm(line)][:window]
        start = 0
        for k in range(min(len(tail), len(head)), 0, -1):
            if [_norm(lines[i]) for i in head[:k]] == tail[-k:]:
                start = head[k - 1] + 1
                break
        if start == 0 and head and tail and _norm(lines[head[0]]) in tail[-1]:
            start = head[0] + 1  # first line is a fragment of the previous band's last line
        if start == 0 and merged and merged[-1].strip():
            merged.append("")  # no shared lines found: keep the bands visibly separate
        merged.extend(lines[start:])
    return "\n".join(merged).strip() + "\n"


def _strip_fence(text: str) -> str:
    match = _FENCE.match(text)
    return match.group(1) if match else text


def ocr_page(
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    pdf_path: Path,
    page_index: int,
    source_title: str,
    options: OcrOptions | None = None,
) -> OcrResult:
    opts = options or OcrOptions()
    models = list(opts.models) if opts.models else None
    texts: list[str] = []
    label: str | None = None
    meta: dict[str, Any] = {}
    cost, tokens = 0.0, 0
    model = prompt_name = prompt_version = ""
    for band in range(opts.bands):
        png = render_page_png(pdf_path, page_index, dpi=opts.dpi, band=band, bands=opts.bands)
        variables = {
            "source_title": source_title,
            "page_number": str(page_index + 1),
            "part": "the whole page" if opts.bands == 1 else f"horizontal strip {band + 1} of {opts.bands}, top first",
        }
        images = [ImageInput(png, "image/png")]
        if opts.output == "json":
            structured = gateway.structured(
                opts.role, opts.prompt, variables, OcrPage, ctx, images=images, models=models
            )
            page = structured.value
            texts.append(page.markdown)
            label = label or page.printed_page_label
            meta.setdefault("running_header", page.running_header)
            meta["has_figures"] = meta.get("has_figures", False) or page.has_figures
            meta["has_handwriting"] = meta.get("has_handwriting", False) or page.has_handwriting
            meta.setdefault("legibility", page.legibility)
            result = structured
        else:
            plain = gateway.text(opts.role, opts.prompt, variables, ctx, images=images, models=models)
            texts.append(_strip_fence(plain.value))
            result = plain
        cost += result.cost_usd or 0.0
        tokens += result.output_tokens or 0
        model, prompt_name, prompt_version = result.model, result.prompt_name, result.prompt_version
    meta.update({"output": opts.output, "dpi": opts.dpi, "bands": opts.bands})
    return OcrResult(
        markdown=texts[0] if len(texts) == 1 else merge_bands(texts),
        printed_page_label=label,
        meta=meta,
        model=model,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        cost_usd=cost,
        output_tokens=tokens,
    )
