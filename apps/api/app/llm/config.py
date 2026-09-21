"""Role → model configuration loaded from roles.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ROLES_FILE = Path(__file__).with_name("roles.yaml")


class RoleConfig(BaseModel):
    model: str
    fallbacks: list[str] = Field(default_factory=list)
    temperature: float = 0.0
    max_tokens: int = 1000
    timeout_s: float = 60.0
    retries: int = Field(default=0, ge=0, le=3)  # extra attempts on the same model after a retryable error
    # Speech models are charged by the character and the provider reports the cost only later, so a voice
    # role states its published price and each call is recorded at that rate.
    usd_per_million_chars: float | None = None

    @property
    def models(self) -> list[str]:
        return [self.model, *self.fallbacks]


class EmbeddingConfig(BaseModel):
    model: str
    dimensions: int
    batch_size: int = 64
    timeout_s: float = 60.0


class RolesConfig(BaseModel):
    version: int
    provider_preferences: dict[str, Any] = Field(default_factory=dict)
    roles: dict[str, RoleConfig]
    embeddings: EmbeddingConfig

    def role(self, name: str) -> RoleConfig:
        try:
            return self.roles[name]
        except KeyError as exc:
            raise KeyError(f"unknown LLM role: {name}") from exc


@lru_cache
def load_roles(path: Path = ROLES_FILE) -> RolesConfig:
    return RolesConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
