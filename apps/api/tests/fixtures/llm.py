"""Scripted LLM transport for tests. Test data only — the application never imports this module."""

from __future__ import annotations

import json
import math
import re
import zlib
from collections.abc import Callable
from typing import Any

from app.llm.config import load_roles
from app.llm.gateway import LLMGateway, MemoryRecorder
from app.llm.prompts import default_registry
from app.llm.transport import ChatRequest, ChatResponse, EmbeddingResponse, TransportError


def hash_embedding(text: str, dims: int = 1024) -> list[float]:
    """Deterministic bag-of-words vector (test data only): texts sharing words have higher cosine similarity."""
    vector = [0.0] * dims
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        vector[zlib.crc32(token.encode()) % dims] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    if norm == 1.0 and not any(vector):
        vector[0] = 1.0
    return [v / norm for v in vector]


class ScriptedTransport:
    """Replies in order with queued responses; any unexpected call fails the test.

    Set ``embedder`` (e.g. ``hash_embedding``) to allow embedding calls.
    """

    def __init__(self) -> None:
        self.script: list[ChatResponse | TransportError] = []
        self.requests: list[ChatRequest] = []
        self.embedder: Callable[[str], list[float]] | None = None
        self.embedded: list[str] = []

    def reply(self, payload: dict[str, Any]) -> None:
        self.script.append(ChatResponse(json.dumps(payload), "scripted/model", "scripted", 120, 60, 0.0, "stop"))

    def reply_text(self, text: str) -> None:
        self.script.append(ChatResponse(text, "scripted/model", "scripted", 120, 60, 0.0, "stop"))

    def fail(self, code: str = "quota_exceeded") -> None:
        self.script.append(TransportError(code, "scripted failure", retryable=False))

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        if not self.script:
            raise AssertionError("unexpected LLM call")
        item = self.script.pop(0)
        if isinstance(item, TransportError):
            raise item
        return item

    def embed(self, model: str, inputs: list[str], timeout_s: float) -> EmbeddingResponse:
        if self.embedder is None:
            raise AssertionError("unexpected embedding call")
        self.embedded.extend(inputs)
        return EmbeddingResponse([self.embedder(text) for text in inputs], model, len(inputs), 0.0)


def scripted_gateway() -> tuple[LLMGateway, ScriptedTransport, MemoryRecorder]:
    transport, recorder = ScriptedTransport(), MemoryRecorder()
    return LLMGateway(transport, load_roles(), default_registry(), recorder), transport, recorder


def user_prompt(request: ChatRequest) -> str:
    content = request.messages[-1]["content"]
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if part.get("type") == "text")
