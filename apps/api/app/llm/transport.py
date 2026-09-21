"""HTTP transport to OpenRouter (OpenAI-compatible API)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class TransportError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: list[dict[str, Any]]
    temperature: float
    max_tokens: int
    timeout_s: float
    response_format: dict[str, Any] | None = None
    provider: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatResponse:
    text: str
    model: str
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    finish_reason: str | None


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: list[list[float]]
    model: str
    input_tokens: int | None
    cost_usd: float | None


@dataclass(frozen=True)
class SpeechResponse:
    audio: bytes
    provider: str | None
    generation_id: str | None  # OpenRouter prices a speech call afterwards, under this id


class ChatTransport(Protocol):
    def chat(self, request: ChatRequest) -> ChatResponse: ...

    def embed(self, model: str, inputs: list[str], timeout_s: float) -> EmbeddingResponse: ...

    def speech(
        self, model: str, input_text: str, voice: str, timeout_s: float, provider: dict[str, Any] | None = None
    ) -> SpeechResponse: ...


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


class OpenRouterTransport:
    def __init__(self, api_key: str, base_url: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise TransportError("not_configured", "OPENROUTER_API_KEY is not set", retryable=False)
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Title": "Scholr",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        try:
            resp = self._client.post(f"{self._base_url}{path}", json=body, headers=self._headers, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise TransportError("timeout", "LLM provider timed out", retryable=True) from exc
        except httpx.TransportError as exc:
            raise TransportError("network", "network error calling LLM provider", retryable=True) from exc
        if resp.status_code == 402:
            # Account out of credit: no model or retry will succeed until it is topped up.
            raise TransportError("quota_exceeded", resp.text[:300], retryable=False)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransportError(f"http_{resp.status_code}", resp.text[:300], retryable=True)
        if resp.status_code >= 400:
            raise TransportError(f"http_{resp.status_code}", resp.text[:300], retryable=False)
        data: dict[str, Any] = resp.json()
        if "error" in data:
            err = data["error"] or {}
            code = int(err.get("code") or 500) if str(err.get("code", "")).isdigit() else 500
            if code == 402:
                raise TransportError("quota_exceeded", str(err.get("message"))[:300], retryable=False)
            raise TransportError(
                f"provider_{code}", str(err.get("message"))[:300], retryable=code >= 500 or code == 429
            )
        return data

    def chat(self, request: ChatRequest) -> ChatResponse:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "usage": {"include": True},
        }
        if request.response_format:
            body["response_format"] = request.response_format
        if request.provider:
            body["provider"] = request.provider
        data = self._post("/chat/completions", body, request.timeout_s)
        choices = data.get("choices") or []
        if not choices:
            raise TransportError("empty_response", "no choices in LLM response", retryable=True)
        choice = choices[0]
        usage = data.get("usage") or {}
        return ChatResponse(
            text=_content_text((choice.get("message") or {}).get("content")),
            model=str(data.get("model") or request.model),
            provider=data.get("provider"),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cost_usd=usage.get("cost"),
            finish_reason=choice.get("finish_reason"),
        )

    def embed(self, model: str, inputs: list[str], timeout_s: float) -> EmbeddingResponse:
        data = self._post("/embeddings", {"model": model, "input": inputs}, timeout_s)
        rows = sorted(data.get("data") or [], key=lambda r: r.get("index", 0))
        if len(rows) != len(inputs):
            raise TransportError("embedding_mismatch", "embedding count mismatch", retryable=True)
        usage = data.get("usage") or {}
        return EmbeddingResponse(
            vectors=[r["embedding"] for r in rows],
            model=str(data.get("model") or model),
            input_tokens=usage.get("prompt_tokens"),
            cost_usd=usage.get("cost"),
        )

    def speech(
        self, model: str, input_text: str, voice: str, timeout_s: float = 60.0, provider: dict[str, Any] | None = None
    ) -> SpeechResponse:
        body: dict[str, Any] = {
            "model": model,
            "input": input_text,
            "voice": voice,
            "response_format": "mp3",
        }
        if provider:
            body["provider"] = provider  # the same "no data collection" rule as every other call
        try:
            resp = self._client.post(
                f"{self._base_url}/audio/speech",
                json=body,
                headers=self._headers,
                timeout=timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise TransportError("timeout", "TTS provider timed out", retryable=True) from exc
        except httpx.TransportError as exc:
            raise TransportError("network", "network error calling TTS provider", retryable=True) from exc
        if resp.status_code == 402:
            raise TransportError("quota_exceeded", resp.text[:300], retryable=False)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransportError(f"http_{resp.status_code}", resp.text[:300], retryable=True)
        if resp.status_code >= 400:
            raise TransportError(f"http_{resp.status_code}", resp.text[:300], retryable=False)
        return SpeechResponse(resp.content, resp.headers.get("X-Provider-Name"), resp.headers.get("X-Generation-Id"))
