"""Time-ordered UUID v7 identifiers."""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Return a UUID v7 (RFC 9562): 48-bit unix ms timestamp + random bits."""
    native = getattr(uuid, "uuid7", None)
    if native is not None:
        return native()
    ts_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= (rand >> 68) & 0xFFF  # 12 bits rand_a
    value <<= 0  # keep layout explicit
    low = rand & ((1 << 62) - 1)
    value = (value & ~((1 << 64) - 1)) | (0b10 << 62) | low  # variant + 62 bits rand_b
    return uuid.UUID(int=value)
