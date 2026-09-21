from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.config import Settings
from app.llm.gateway import CallContext
from app.modules.learn.audio import extract_speech_text, get_or_synthesize_audio
from app.modules.learn.schemas import KeyTermOut, LessonOut, LessonSectionOut, WorkedExampleOut


def _dummy_lesson() -> LessonOut:
    return LessonOut(
        id=uuid4(),
        status="ready",
        summary="This is a summary with $x^2 = 4$.",
        sections=[
            LessonSectionOut(heading="Section 1", body="Body of section 1 with $\\frac{1}{2}$.", sources=[]),
            LessonSectionOut(heading="Section 2", body="Body of section 2.", sources=[]),
        ],
        key_terms=[KeyTermOut(term="Hypotenuse", meaning="Longest side.")],
        worked_examples=[
            WorkedExampleOut(
                problem="Find $x$",
                steps=["Step 1", "Step 2"],
                final_answer="2",
                unit="m",
                checked="sympy",
                sources=[],
                level="basic",
            )
        ],
        diagrams=[],
        pitfalls=["Trap 1", "Trap 2"],
        generated_at=datetime.now(UTC),
    )


def test_extract_speech_text() -> None:
    lesson = _dummy_lesson()

    summary_text = extract_speech_text(lesson, part="summary")
    assert "This is a summary" in summary_text

    section_text = extract_speech_text(lesson, part="section", index=0)
    assert "Section 1" in section_text
    assert "Body of section 1" in section_text

    example_text = extract_speech_text(lesson, part="example", index=0)
    assert "Worked example 1" in example_text
    assert "Find $x$" in example_text
    assert "Step 1" in example_text
    assert "Answer: 2 m" in example_text

    all_text = extract_speech_text(lesson, part="all")
    assert "This is a summary" in all_text
    assert "Section 1" in all_text
    assert "Section 2" in all_text
    assert "Key terms" in all_text
    assert "Watch out for" in all_text


def test_audio_caching(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.speech.return_value = b"fake-mp3-audio"
    ctx = CallContext(request_id="r", tenant_id=uuid4())

    settings = MagicMock(spec=Settings)
    settings.private_content_dir = tmp_path

    # First call goes through the gateway (recorded and priced there), as the lesson_voice role
    audio1 = get_or_synthesize_audio(gateway, ctx, settings, "Hello world", voice="bf_emma")
    assert audio1 == b"fake-mp3-audio"
    assert gateway.speech.call_count == 1
    assert gateway.speech.call_args.args[0] == "lesson_voice"

    # Second call hits the cache file on disk without another model call
    audio2 = get_or_synthesize_audio(gateway, ctx, settings, "Hello world", voice="bf_emma")
    assert audio2 == b"fake-mp3-audio"
    assert gateway.speech.call_count == 1
