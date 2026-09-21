"""Her spoken question, turned into text she checks before sending (docs/STUDENT-APP.md §16).

Replaces the browser's speech recognition, which sent her voice to Google or Microsoft under their terms. Here the
recording goes through the LLM gateway like every other model call — the `speech_to_text` role on Flash-Lite, with
the provider preferences (no data collection), recorded with its cost in llm_call — and is never stored: not on
disk, not in the database, not in a log. Only the text comes back, into her message box, where she reads and edits
it; nothing is sent to the Tutor until she presses Send, and then it goes through the normal turn and its safety
checks like anything she typed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.core.errors import ApiError
from app.llm.gateway import AudioInput, CallContext, LLMError, LLMGateway
from app.tools import wav

ROLE = "speech_to_text"
PROMPT = "speech_transcribe"
MAX_SECONDS = 60  # a spoken question, not a lecture
MAX_BYTES = 4_000_000  # 60 s of 16 kHz mono 16-bit is ~1.9 MB; room for a browser that records at 32 kHz
MAX_CHARS = 2000  # the Tutor's own limit on a message


class Transcript(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = ""
    unclear: bool = False


def check_recording(audio: bytes) -> wav.WavInfo:
    """The recording is a PCM WAV no longer than a spoken question, or a 400/413 before any model call."""
    if len(audio) > MAX_BYTES:
        raise ApiError(413, "recording_too_long", f"Keep a spoken question under {MAX_SECONDS} seconds.")
    try:
        info = wav.read_header(audio)
    except wav.WavError:
        raise ApiError(400, "bad_recording", "That recording could not be read. Try again, or type it.") from None
    if info.seconds > MAX_SECONDS + 1:
        raise ApiError(413, "recording_too_long", f"Keep a spoken question under {MAX_SECONDS} seconds.")
    if info.seconds < 0.3:
        raise ApiError(422, "nothing_heard", "That was too short to hear anything. Hold the mic a little longer.")
    return info


def transcribe(gateway: LLMGateway, ctx: CallContext, audio: bytes) -> Transcript:
    check_recording(audio)
    try:
        result = gateway.structured(ROLE, PROMPT, {}, Transcript, ctx, images=[AudioInput(audio, "wav")])
    except LLMError as exc:
        raise ApiError(
            503, "speech_unavailable", "Voice input isn't available right now. Please type instead."
        ) from exc
    text = " ".join(result.value.text.split())[:MAX_CHARS]
    if not text:
        raise ApiError(422, "nothing_heard", "I couldn't hear a question in that. Try again, or type it.")
    return Transcript(text=text, unclear=result.value.unclear)
