"""Checks around the homework photo (docs/GO-LIVE-ENGAGEMENT.md F3): what is accepted, and what she is shown."""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.modules.learn import homework
from app.tools.images import sniff_image

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff" + b"0" * 64
WEBP = b"RIFF" + b"0000" + b"WEBP" + b"0" * 64


def test_the_photo_must_be_an_image_we_accept() -> None:
    assert homework.check_photo(PNG) == "image/png"
    assert homework.check_photo(JPEG) == "image/jpeg"
    assert homework.check_photo(WEBP) == "image/webp"


def test_anything_else_is_refused_before_a_model_is_called() -> None:
    with pytest.raises(ApiError) as pdf:
        homework.check_photo(b"%PDF-1.7 not an image")
    assert pdf.value.status == 415

    with pytest.raises(ApiError) as empty:
        homework.check_photo(b"")
    assert empty.value.status == 422

    with pytest.raises(ApiError) as big:
        homework.check_photo(PNG + b"0" * homework.MAX_BYTES)
    assert big.value.status == 413


def test_the_declared_type_is_never_trusted() -> None:
    # A .png filename over JPEG bytes is read as what it is; the client's claim never decides.
    assert sniff_image(JPEG) == ("image/jpeg", "jpg")
    assert sniff_image(b"GIF89a") is None


def test_she_sees_a_short_look_at_what_was_read_never_the_whole_page() -> None:
    assert homework.preview("  Solve   x^2 - 5x + 6 = 0 ") == "Solve x^2 - 5x + 6 = 0"
    long_page = " ".join(f"Question {n}" for n in range(200))
    shown = homework.preview(long_page)
    assert len(shown) <= homework.PREVIEW_CHARS + 1 and shown.endswith("…")


def test_the_reader_has_nowhere_to_put_an_answer() -> None:
    # The reply schema is the guard: a model that answers anyway has no field to answer in, and extra keys are
    # dropped rather than reaching her.
    read = homework.HomeworkRead.model_validate(
        {"text": "Solve x^2 = 9", "readable": True, "subject_words": [], "answer": "x = 3", "method": "square root"}
    )
    assert not hasattr(read, "answer") and not hasattr(read, "method")
    assert set(read.model_dump()) == {"text", "readable", "subject_words"}
