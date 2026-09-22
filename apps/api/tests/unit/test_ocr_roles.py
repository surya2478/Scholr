from __future__ import annotations

from app.llm.config import load_roles
from app.llm.prompts import default_registry
from app.modules.knowledge.manifest import load_all

# User rule (21 Sep 2026): only two LLMs, each live and batch. Gemini 2.5 Flash-Lite for every role by default;
# GLM 5.3 Flash for lesson_writer and exam_walker. No other model, no fallbacks. Two non-LLM models are kept by
# the user's decision: Kokoro (read-aloud) and bge-m3 (embeddings, configured apart from the roles).
FLASH_LITE = ("google/gemini-2.5-flash-lite", "google/gemini-2.5-flash-lite:batch")
GLM = ("z-ai/glm-5.3-flash", "z-ai/glm-5.3-flash:batch")
GLM_ROLES = {"lesson_writer", "exam_walker"}
NOT_LLM = {"lesson_voice": "hexgrad/kokoro-82m"}


def test_every_source_ocr_role_and_prompt_exist() -> None:
    roles = load_roles().roles
    registry = default_registry()
    for manifest in load_all():
        for source in manifest.sources:
            assert source.ocr_role in roles, f"{source.key}: unknown OCR role {source.ocr_role}"
            assert registry.get(source.ocr_prompt).name == source.ocr_prompt


def test_every_role_uses_only_the_two_allowed_models() -> None:
    config = load_roles()
    for name in config.roles:
        role = config.role(name)
        assert not role.fallbacks, f"{name} would fall back to {role.fallbacks}"
        if name in NOT_LLM:
            assert role.model == NOT_LLM[name] and role.batch_model is None, name
            continue
        live, batch = GLM if name in GLM_ROLES else FLASH_LITE
        assert role.model == live, f"{name} uses {role.model}"
        assert role.batch_model in (None, batch), f"{name} batches on {role.batch_model}"
