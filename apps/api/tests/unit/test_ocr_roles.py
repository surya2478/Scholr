from __future__ import annotations

from app.llm.config import load_roles
from app.llm.prompts import default_registry
from app.modules.knowledge.manifest import load_all

# User rule (19 Sep 2026): every LLM role — PDF extraction, batch jobs and marking — runs on Gemini 2.5 Flash-Lite
# and never falls back to another model. Embeddings are a separate model (bge-m3) and not an LLM role.
ONLY_MODEL = "google/gemini-2.5-flash-lite"
# The one exception, the user's decision of 21 Sep 2026 after the lesson v4 pilot (docs/STUDENT-APP.md §15).
# lesson_voice is a speech model (lesson read-aloud), not an LLM; put behind the gateway on 21 Sep 2026.
EXCEPTIONS = {"lesson_writer": "google/gemini-2.5-flash", "lesson_voice": "hexgrad/kokoro-82m"}


def test_every_source_ocr_role_and_prompt_exist() -> None:
    roles = load_roles().roles
    registry = default_registry()
    for manifest in load_all():
        for source in manifest.sources:
            assert source.ocr_role in roles, f"{source.key}: unknown OCR role {source.ocr_role}"
            assert registry.get(source.ocr_prompt).name == source.ocr_prompt


def test_every_role_uses_only_flash_lite() -> None:
    config = load_roles()
    for name in config.roles:
        role = config.role(name)
        assert role.model == EXCEPTIONS.get(name, ONLY_MODEL), f"{name} uses {role.model}"
        assert not role.fallbacks, f"{name} would fall back to {role.fallbacks}"
