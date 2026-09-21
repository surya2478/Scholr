"""Read a WAV file's header: is it one, and how long is it. Deterministic, no audio libraries.

The Tutor's speech input sends a short WAV recorded in the browser (docs/STUDENT-APP.md §16). Before it goes to a
model, the API checks it really is a WAV and is not longer than a spoken question, from the header alone.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


class WavError(ValueError):
    pass


@dataclass(frozen=True)
class WavInfo:
    channels: int
    sample_rate: int
    bits_per_sample: int
    data_bytes: int

    @property
    def seconds(self) -> float:
        per_second = self.sample_rate * self.channels * self.bits_per_sample // 8
        return self.data_bytes / per_second if per_second else 0.0


def read_header(data: bytes) -> WavInfo:
    """The format and length of a PCM WAV, from its RIFF chunks. Raises WavError for anything else."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavError("not a WAV file")
    fmt: tuple[int, int, int, int] | None = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id, size = data[offset : offset + 4], struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        body = offset + 8
        if chunk_id == b"fmt ":
            if size < 16 or body + 16 > len(data):
                raise WavError("short fmt chunk")
            audio_format, channels, rate, _, _, bits = struct.unpack("<HHIIHH", data[body : body + 16])
            if audio_format != 1:
                raise WavError("not PCM")
            fmt = (channels, rate, bits, 0)
        elif chunk_id == b"data":
            if fmt is None:
                raise WavError("data before fmt")
            channels, rate, bits, _ = fmt
            if not channels or not rate or bits not in (8, 16, 24, 32):
                raise WavError("unusable format")
            return WavInfo(channels, rate, bits, min(size, len(data) - body))
        offset = body + size + (size % 2)
    raise WavError("no data chunk")
