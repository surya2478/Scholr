"""Private storage for answer photos. Files live under UPLOADS_DIR (gitignored content/private by default);
the database holds only ``private://uploads/<student>/<attempt>-<n>.<ext>`` references."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

MAX_BYTES = 8 * 1024 * 1024
MAX_PHOTOS = 4
URI_PREFIX = "private://uploads/"


class UploadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """(media type, extension) from magic bytes; the client's declared type is never trusted."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def save_photo(uploads_dir: Path, student_id: UUID, attempt_id: UUID, index: int, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise UploadError("photo_too_large", f"each photo must be under {MAX_BYTES // (1024 * 1024)} MB")
    kind = sniff_image(data)
    if kind is None:
        raise UploadError("invalid_image", "photos must be PNG, JPEG or WebP images")
    relative = Path(str(student_id)) / f"{attempt_id}-{index}.{kind[1]}"
    path = uploads_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return URI_PREFIX + relative.as_posix()


def _path_for(uploads_dir: Path, uri: str) -> Path:
    if not uri.startswith(URI_PREFIX):
        raise UploadError("photo_missing", "unknown photo reference")
    root = uploads_dir.resolve()
    path = (root / uri.removeprefix(URI_PREFIX)).resolve()
    if not path.is_relative_to(root):
        raise UploadError("photo_missing", "unknown photo reference")
    return path


def load_photo(uploads_dir: Path, uri: str) -> tuple[bytes, str]:
    path = _path_for(uploads_dir, uri)
    if not path.is_file():
        raise UploadError("photo_missing", "a photo for this attempt is missing")
    data = path.read_bytes()
    kind = sniff_image(data)
    if kind is None:
        raise UploadError("photo_missing", "a photo for this attempt is unreadable")
    return data, kind[0]


def delete_photos(uploads_dir: Path, uris: list[str]) -> None:
    for uri in uris:
        try:
            _path_for(uploads_dir, uri).unlink(missing_ok=True)
        except (UploadError, OSError):
            continue
