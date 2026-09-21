"""The only way application code calls an LLM (ARCHITECTURE §19)."""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.llm.config import RoleConfig, RolesConfig
from app.llm.prompts import Prompt, PromptRegistry
from app.llm.transport import ChatRequest, ChatResponse, ChatTransport, TransportError

ErrorCode = Literal["not_configured", "quota_exceeded", "provider_error", "invalid_output", "bad_request"]
_PASSTHROUGH_CODES: frozenset[str] = frozenset({"not_configured", "quota_exceeded"})


class LLMError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CallContext:
    request_id: str
    tenant_id: UUID
    student_id: UUID | None = None


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    media_type: str = "image/png"

    def as_part(self) -> dict[str, Any]:
        encoded = base64.b64encode(self.data).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{self.media_type};base64,{encoded}"}}


@dataclass(frozen=True)
class AudioInput:
    """A recording sent with a prompt (speech to text). Passed through, never stored by the gateway."""

    data: bytes
    format: Literal["wav", "mp3"] = "wav"

    def as_part(self) -> dict[str, Any]:
        encoded = base64.b64encode(self.data).decode("ascii")
        return {"type": "input_audio", "input_audio": {"data": encoded, "format": self.format}}


Attachment = ImageInput | AudioInput


@dataclass(frozen=True)
class LlmCallRecord:
    request_id: str
    tenant_id: UUID
    student_id: UUID | None
    role: str
    model: str
    provider: str | None
    prompt_name: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int
    status: Literal["ok", "error"]
    fallback_used: bool
    error_code: str | None


class CallRecorder(Protocol):
    def record(self, rec: LlmCallRecord) -> None: ...


@dataclass
class MemoryRecorder:
    records: list[LlmCallRecord] = field(default_factory=list)

    def record(self, rec: LlmCallRecord) -> None:
        self.records.append(rec)


@dataclass(frozen=True)
class LLMResult[T]:
    value: T
    text: str
    model: str
    fallback_used: bool
    prompt_name: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _extract_json(text: str) -> str:
    m = _FENCE.match(text)
    if m:
        return m.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    return text[start:] if start > 0 else text


# A backslash that does not start a valid JSON escape — typically LaTeX such as \sqrt or \underline in a string.
_INVALID_ESCAPE = re.compile(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})')


def _validate[T: BaseModel](schema: type[T], text: str) -> T:
    """Strict parse; if that fails, parse once more with invalid backslash escapes doubled (no extra LLM call)."""
    raw = _extract_json(text)
    try:
        return schema.model_validate_json(raw)
    except ValidationError:
        fixed = _INVALID_ESCAPE.sub(r"\\\\", raw)
        if fixed == raw:
            raise
        return schema.model_validate_json(fixed)


class LLMGateway:
    def __init__(
        self,
        transport: ChatTransport,
        roles: RolesConfig,
        prompts: PromptRegistry,
        recorder: CallRecorder,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._transport = transport
        self._roles = roles
        self._prompts = prompts
        self._recorder = recorder
        self._clock = clock

    # -- public API -----------------------------------------------------------------

    def text(
        self,
        role: str,
        prompt_name: str,
        variables: dict[str, str],
        ctx: CallContext,
        *,
        images: Sequence[Attachment] = (),
        prompt_version: str | None = None,
        models: Sequence[str] | None = None,
    ) -> LLMResult[str]:
        prompt = self._prompts.get(prompt_name, prompt_version)
        messages = self._messages(prompt, variables, images)
        resp, model, fallback, latency = self._complete(
            role, prompt, messages, None, ctx, models=list(models) if models else None
        )
        return LLMResult(
            resp.text,
            resp.text,
            model,
            fallback,
            prompt.name,
            prompt.version,
            resp.input_tokens,
            resp.output_tokens,
            resp.cost_usd,
            latency,
        )

    def speech(self, role: str, text: str, voice: str, ctx: CallContext) -> bytes:
        """Read text aloud with the role's voice model. Recorded in llm_call like any other call (cost from the
        role's per-character price), sent with the same provider preferences, and never falls back silently."""
        cfg: RoleConfig = self._roles.role(role)
        last_code = "provider_error"
        for idx, model in enumerate(cfg.models):
            for _attempt in range(cfg.retries + 1):
                started = self._clock()
                try:
                    resp = self._transport.speech(
                        model, text, voice, cfg.timeout_s, provider=self._roles.provider_preferences or None
                    )
                except TransportError as exc:
                    self._record(
                        ctx, role, model, None, "speech", voice, None, None, None, started, "error", idx > 0, exc.code
                    )
                    last_code = exc.code
                    if not exc.retryable:
                        code: ErrorCode = exc.code if exc.code in _PASSTHROUGH_CODES else "bad_request"  # type: ignore[assignment]
                        raise LLMError(code, f"{role}: {exc.code}") from exc
                    continue
                break
            else:
                continue
            rate = cfg.usd_per_million_chars
            cost = len(text) * rate / 1_000_000 if rate is not None else None
            self._record(
                ctx, role, model, resp.provider, "speech", voice, None, None, cost, started, "ok", idx > 0, None
            )
            if not resp.audio:
                raise LLMError("provider_error", f"{role}: empty audio")
            return resp.audio
        raise LLMError("provider_error", f"{role}: all models failed (last: {last_code})")

    def structured[T: BaseModel](
        self,
        role: str,
        prompt_name: str,
        variables: dict[str, str],
        schema: type[T],
        ctx: CallContext,
        *,
        images: Sequence[Attachment] = (),
        prompt_version: str | None = None,
        models: Sequence[str] | None = None,
        temperature: float | None = None,
    ) -> LLMResult[T]:
        """``models`` overrides the role's model list (model screening in evals only)."""
        prompt = self._prompts.get(prompt_name, prompt_version)
        json_schema = schema.model_json_schema()
        messages = self._messages(prompt, variables, images, json_schema=json_schema)
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": False, "schema": json_schema},
        }
        resp, model, fallback, latency = self._complete(
            role,
            prompt,
            messages,
            response_format,
            ctx,
            models=list(models) if models else None,
            temperature=temperature,
        )
        try:
            value = _validate(schema, resp.text)
        except ValidationError as first_error:
            repair = [
                *messages,
                {"role": "assistant", "content": resp.text},
                {
                    "role": "user",
                    "content": "Your reply did not match the required JSON schema. Errors:\n"
                    f"{_summarise_errors(first_error)}\nReturn only corrected JSON.",
                },
            ]
            resp2, model, fallback2, latency2 = self._complete(
                role, prompt, repair, response_format, ctx, models=[model], temperature=temperature
            )
            latency += latency2
            fallback = fallback or fallback2
            try:
                value = _validate(schema, resp2.text)
            except ValidationError as exc:
                raise LLMError("invalid_output", f"{prompt.name}: output failed schema validation twice") from exc
            resp = resp2
        return LLMResult(
            value,
            resp.text,
            model,
            fallback,
            prompt.name,
            prompt.version,
            resp.input_tokens,
            resp.output_tokens,
            resp.cost_usd,
            latency,
        )

    def embed(self, texts: Sequence[str], ctx: CallContext) -> list[list[float]]:
        cfg = self._roles.embeddings
        vectors: list[list[float]] = []
        for i in range(0, len(texts), cfg.batch_size):
            batch = list(texts[i : i + cfg.batch_size])
            started = self._clock()
            try:
                resp = self._transport.embed(cfg.model, batch, cfg.timeout_s)
            except TransportError as exc:
                self._record(
                    ctx,
                    "embeddings",
                    cfg.model,
                    None,
                    "embed",
                    "v1",
                    None,
                    None,
                    None,
                    started,
                    "error",
                    False,
                    exc.code,
                )
                raise LLMError("provider_error", f"embedding failed: {exc.code}") from exc
            for v in resp.vectors:
                if len(v) != cfg.dimensions:
                    raise LLMError("invalid_output", f"embedding has {len(v)} dims, expected {cfg.dimensions}")
            self._record(
                ctx,
                "embeddings",
                resp.model,
                None,
                "embed",
                "v1",
                resp.input_tokens,
                None,
                resp.cost_usd,
                started,
                "ok",
                False,
                None,
            )
            vectors.extend(resp.vectors)
        return vectors

    # -- internals ------------------------------------------------------------------

    def _messages(
        self,
        prompt: Prompt,
        variables: dict[str, str],
        images: Sequence[Attachment],
        json_schema: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        system, user = prompt.render(variables)
        if json_schema is not None:
            system += (
                "\n\nRespond with a single JSON object that conforms to this JSON Schema. "
                "Do not add commentary.\n" + json.dumps(json_schema)
            )
        user_content: Any = user
        if images:
            user_content = [{"type": "text", "text": user}, *(img.as_part() for img in images)]
        return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]

    def _complete(
        self,
        role: str,
        prompt: Prompt,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None,
        ctx: CallContext,
        models: list[str] | None = None,
        temperature: float | None = None,
    ) -> tuple[ChatResponse, str, bool, int]:
        cfg: RoleConfig = self._roles.role(role)
        candidates = models or cfg.models
        last_code = "provider_error"
        for idx, model in enumerate(candidates):
            for _attempt in range(cfg.retries + 1):
                started = self._clock()
                request = ChatRequest(
                    model=model,
                    messages=messages,
                    temperature=cfg.temperature if temperature is None else temperature,
                    max_tokens=cfg.max_tokens,
                    timeout_s=cfg.timeout_s,
                    response_format=response_format,
                    provider=self._roles.provider_preferences or None,
                )
                try:
                    resp = self._transport.chat(request)
                except TransportError as exc:
                    self._record(
                        ctx,
                        role,
                        model,
                        None,
                        prompt.name,
                        prompt.version,
                        None,
                        None,
                        None,
                        started,
                        "error",
                        idx > 0,
                        exc.code,
                    )
                    last_code = exc.code
                    if not exc.retryable:
                        code: ErrorCode = exc.code if exc.code in _PASSTHROUGH_CODES else "bad_request"  # type: ignore[assignment]
                        raise LLMError(code, f"{role}: {exc.code}") from exc
                    continue
                break
            else:
                continue  # every attempt on this model failed with a retryable error: try the next model
            latency = self._record(
                ctx,
                role,
                model,
                resp.provider,
                prompt.name,
                prompt.version,
                resp.input_tokens,
                resp.output_tokens,
                resp.cost_usd,
                started,
                "ok",
                idx > 0,
                None,
            )
            return resp, model, idx > 0, latency
        raise LLMError("provider_error", f"{role}: all models failed (last: {last_code})")

    def _record(
        self,
        ctx: CallContext,
        role: str,
        model: str,
        provider: str | None,
        prompt_name: str,
        prompt_version: str,
        input_tokens: int | None,
        output_tokens: int | None,
        cost_usd: float | None,
        started: float,
        status: Literal["ok", "error"],
        fallback_used: bool,
        error_code: str | None,
    ) -> int:
        latency_ms = int((self._clock() - started) * 1000)
        self._recorder.record(
            LlmCallRecord(
                ctx.request_id,
                ctx.tenant_id,
                ctx.student_id,
                role,
                model,
                provider,
                prompt_name,
                prompt_version,
                input_tokens,
                output_tokens,
                cost_usd,
                latency_ms,
                status,
                fallback_used,
                error_code,
            )
        )
        return latency_ms


def _summarise_errors(error: ValidationError, limit: int = 8) -> str:
    lines = []
    for err in error.errors()[:limit]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        lines.append(f"- {loc or '(root)'}: {err.get('msg')}")
    return "\n".join(lines)
