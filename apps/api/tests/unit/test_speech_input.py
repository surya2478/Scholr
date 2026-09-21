"""Speech input to the Tutor (docs/STUDENT-APP.md §16): the recording is checked by code before any model call."""

from __future__ import annotations

import struct

import pytest

from app.core.errors import ApiError
from app.modules.tutoring import speech
from app.tools import wav


def make_wav(seconds: float, rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    data = bytes(int(seconds * rate) * channels * bits // 8)
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_a_wav_header_gives_its_length() -> None:
    info = wav.read_header(make_wav(2.5))
    assert (info.channels, info.sample_rate, info.bits_per_sample) == (1, 16000, 16)
    assert info.seconds == pytest.approx(2.5)
    for bad in (b"", b"ID3 not a wav at all", make_wav(1)[:20]):
        with pytest.raises(wav.WavError):
            wav.read_header(bad)


def test_only_a_short_spoken_question_goes_to_a_model() -> None:
    assert speech.check_recording(make_wav(5)).seconds == pytest.approx(5)
    for audio, status in ((make_wav(61.5), 413), (make_wav(0.1), 422), (b"webm-bytes", 400)):
        with pytest.raises(ApiError) as err:
            speech.check_recording(audio)
        assert err.value.status == status
