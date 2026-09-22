"""Source manifests (content/manifests/*.yaml): licence, owner and authority for every document."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import CONTENT_DIR

MANIFEST_DIR = CONTENT_DIR / "manifests"


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    publisher: str | None = None
    edition: str | None = None
    owner: str
    licence: str
    acquired_via: str
    private: bool = True
    file: str
    authority_tier: Literal["A", "B", "C", "D", "E"]
    content_kind: str
    exam_series: str | None = None
    component: str | None = None
    notes: str | None = None
    # Question numbers whose section has no unit in the current syllabus (old papers' Media option): their items
    # are saved with no objectives, whatever the extractor tagged, so they never stand for a current topic.
    untagged_questions: list[str] = Field(default_factory=list)
    # LLM role used to OCR scanned pages (app/llm/roles.yaml); chosen per source from app.jobs.ocr_eval results.
    ocr_role: str = "page_ocr"
    ocr_prompt: str = "page_ocr"  # prompt name in app/llm/prompts/
    ocr_postprocess: list[Literal["unicode_math_to_latex", "repair_json_escapes"]] = Field(default_factory=list)
    ocr_output: Literal["json", "markdown"] = "json"
    ocr_dpi: int = Field(default=150, ge=72, le=300)
    ocr_bands: int = Field(default=1, ge=1, le=4)


class ManifestFile(BaseModel):
    subject: str
    curriculum: str
    syllabus: str
    sources: list[SourceIn]


def load_manifest(path: Path) -> ManifestFile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw.pop("defaults", None)  # anchor holder; values are merged into sources via <<: *anchor
    return ManifestFile.model_validate(raw)


def load_all(directory: Path = MANIFEST_DIR) -> list[ManifestFile]:
    return [load_manifest(p) for p in sorted(directory.glob("*.yaml"))]
