"""Build the production LLM gateway from settings."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.llm.config import load_roles
from app.llm.gateway import CallRecorder, LLMGateway
from app.llm.prompts import default_registry
from app.llm.recorder import DbCallRecorder
from app.llm.transport import OpenRouterTransport


def build_gateway(recorder: CallRecorder | None = None) -> LLMGateway:
    settings = get_settings()
    transport = OpenRouterTransport(settings.openrouter_api_key.get_secret_value(), settings.openrouter_base_url)
    return LLMGateway(
        transport=transport,
        roles=load_roles(),
        prompts=default_registry(),
        recorder=recorder or DbCallRecorder(get_session_factory()),
    )
