"""What kind of image a byte string actually is. Deterministic, and the client's declared type is never trusted.

Shared by answer photos, which are stored (``assessment/storage.py``), and homework photos, which are not
(``learn/homework.py``).
"""

from __future__ import annotations

ALLOWED = ("PNG", "JPEG", "WebP")


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """(media type, extension) from the magic bytes, or None when it is not an image we accept."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None
