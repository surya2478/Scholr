"""Lesson text-to-speech: a lesson part read aloud by the `lesson_voice` role (roles.yaml).

The call goes through the LLM gateway like every other model call, so it is recorded in llm_call with its cost
and sent with the provider preferences. Audio is cached on disk by the hash of voice and spoken text, so each
clip is paid for once.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from app.core.config import Settings
from app.llm.gateway import CallContext, LLMGateway
from app.modules.learn.schemas import LessonOut
from app.tools.math_speech import math_to_speech

VOICE_ROLE = "lesson_voice"
DEFAULT_VOICE = "bf_emma"
ALLOWED_VOICES = {"bf_emma", "bf_isabella", "bm_george", "bm_lewis"}


def _cache_dir(settings: Settings) -> Path:
    d = settings.private_content_dir / "cache" / "audio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_speech_text(
    lesson: LessonOut,
    part: Literal["summary", "section", "example", "all"] = "all",
    index: int = 0,
) -> str:
    """Extracts raw text for the requested lesson component."""
    if part == "summary":
        return lesson.summary or ""

    if part == "section":
        if 0 <= index < len(lesson.sections):
            sec = lesson.sections[index]
            return f"{sec.heading}. {sec.body}"
        return ""

    if part == "example":
        if 0 <= index < len(lesson.worked_examples):
            ex = lesson.worked_examples[index]
            steps = ". ".join(ex.steps)
            ans = f"Answer: {ex.final_answer} {ex.unit}".strip()
            return f"Worked example {index + 1}. {ex.problem}. {steps}. {ans}"
        return ""

    # "all": combine summary, sections, key terms, and pitfalls
    parts: list[str] = []
    if lesson.summary:
        parts.append(lesson.summary)
    for sec in lesson.sections:
        parts.append(f"{sec.heading}. {sec.body}")
    if lesson.key_terms:
        terms_text = "Key terms: " + "; ".join(f"{t.term}: {t.meaning}" for t in lesson.key_terms)
        parts.append(terms_text)
    if lesson.pitfalls:
        parts.append("Watch out for: " + "; ".join(lesson.pitfalls))
    return "\n\n".join(parts)


def get_or_synthesize_audio(
    gateway: LLMGateway,
    ctx: CallContext,
    settings: Settings,
    text: str,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """Returns cached MP3 audio bytes, or has the `lesson_voice` role read the text aloud."""
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE

    cleaned = math_to_speech(text)
    if not cleaned.strip():
        return b""

    # Cache by hash of voice + cleaned text
    key = hashlib.sha256(f"{voice}:{cleaned}".encode()).hexdigest()
    cache_file = _cache_dir(settings) / f"{key}.mp3"

    if cache_file.exists() and cache_file.stat().st_size > 0:
        return cache_file.read_bytes()

    audio_bytes = gateway.speech(VOICE_ROLE, cleaned, voice, ctx)

    if audio_bytes:
        cache_file.write_bytes(audio_bytes)

    return audio_bytes
