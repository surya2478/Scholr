"""Photograph your homework, land on the right topic (docs/GO-LIVE-ENGAGEMENT.md F3).

She is set school homework most days, so that is the trigger we answer: she photographs the worksheet and
Scholr offers the topic it is on — her lesson, the bank questions on it, and the Tutor scoped there.

What this is careful about:

- **It never does her homework.** The reader transcribes the questions and nothing else (``homework_read/v1``),
  the reply has no field an answer could arrive in, and what she is handed is a topic page, which starts with
  the help ladder like any other (PRINCIPLES §18, §27). Coaching her through her own work is the point; doing
  it for her is not.
- **The topic is decided by code, not by a model.** The model may not even name a subject: the text is matched
  against her own books by ``knowledge.topics_for_text``, and only at the bar lessons already hold —
  HIGH or MEDIUM retrieval. Below it she is told plainly to pick the topic herself.
- **She confirms.** Matches are offered, never followed automatically, and the best one is not preselected.
- **Nothing is kept.** The photo is not written to disk, the text is not stored in any table, and no retrieval
  log row is written for it. ``llm_call`` records the call's cost and metadata, as it does for every call, and
  holds no prompt or reply text.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ApiError
from app.llm.gateway import CallContext, ImageInput, LLMError, LLMGateway
from app.tools.images import ALLOWED, sniff_image

READ_ROLE = "homework_reader"
READ_PROMPT = "homework_read"
MAX_BYTES = 8 * 1024 * 1024  # as answer photos (assessment/storage.py)
MAX_CHARS = 1200  # the prompt's own limit: the questions, not a whole chapter
PREVIEW_CHARS = 240  # enough for her to see the read worked; never the whole worksheet


class HomeworkRead(BaseModel):
    """What the reader may return. There is deliberately no field for an answer, a method or a topic."""

    model_config = ConfigDict(extra="ignore")
    text: str = Field(default="", max_length=4000)
    readable: bool = True
    subject_words: list[str] = Field(default_factory=list, max_length=8)


def check_photo(data: bytes) -> str:
    """The photo is an image we accept and small enough, or a 413/415 before any model call. Returns its type."""
    if not data:
        raise ApiError(422, "no_photo", "No photo arrived. Take the picture again.")
    if len(data) > MAX_BYTES:
        raise ApiError(413, "photo_too_large", f"Keep the photo under {MAX_BYTES // (1024 * 1024)} MB.")
    kind = sniff_image(data)
    if kind is None:
        raise ApiError(415, "invalid_image", f"Photos must be {', '.join(ALLOWED)} images.")
    return kind[0]


def read_photo(gateway: LLMGateway, ctx: CallContext, *, data: bytes) -> HomeworkRead:
    """Read the questions off the photo. The bytes are passed through to the gateway and never stored."""
    media_type = check_photo(data)
    try:
        result = gateway.structured(
            READ_ROLE, READ_PROMPT, {}, HomeworkRead, ctx, images=[ImageInput(data, media_type)]
        )
    except LLMError as exc:
        raise ApiError(
            503, "homework_read_unavailable", "Reading photos isn't available right now. Pick the topic yourself."
        ) from exc
    read = result.value
    text = " ".join(read.text.split())[:MAX_CHARS]
    return HomeworkRead(text=text, readable=read.readable and bool(text), subject_words=read.subject_words)


def preview(text: str, *, limit: int = PREVIEW_CHARS) -> str:
    """A short look at what was read, so she can see the photo worked. Never the whole page."""
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[:limit].rstrip() + "…"
