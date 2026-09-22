from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.llm.config import EmbeddingConfig, RoleConfig, RolesConfig, load_roles
from app.llm.gateway import BatchItem, CallContext, ImageInput, LLMError, LLMGateway, MemoryRecorder
from app.llm.prompts import PromptError, PromptRegistry, parse_prompt_file
from app.llm.transport import ChatRequest, ChatResponse, EmbeddingResponse, SpeechResponse, TransportError

PROMPT = """---
name: demo
version: v1
role: tutor
---
## system
You are a careful tutor.
## user
Question: <question>{{question}}</question>
"""


class Answer(BaseModel):
    answer: str
    confidence: float


class FakeTransport:
    def __init__(self, script: list[ChatResponse | TransportError]) -> None:
        self.script = list(script)
        self.requests: list[ChatRequest] = []

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        item = self.script.pop(0)
        if isinstance(item, TransportError):
            raise item
        return item

    def embed(self, model: str, inputs: list[str], timeout_s: float) -> EmbeddingResponse:
        return EmbeddingResponse([[0.1, 0.2, 0.3] for _ in inputs], model, 5, 0.0)


def ok(text: str, model: str = "m1") -> ChatResponse:
    return ChatResponse(text, model, "prov", 10, 5, 0.001, "stop")


@pytest.fixture
def registry(tmp_path: Path) -> PromptRegistry:
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "v1.md").write_text(PROMPT, encoding="utf-8")
    return PromptRegistry(tmp_path)


ROLES = RolesConfig(
    version=1,
    provider_preferences={"data_collection": "deny"},
    roles={"tutor": RoleConfig(model="m1", fallbacks=["m2"])},
    embeddings=EmbeddingConfig(model="e1", dimensions=3, batch_size=2),
)
CTX = CallContext(request_id="req-1", tenant_id=uuid4())


def gateway(transport: FakeTransport, registry: PromptRegistry, recorder: MemoryRecorder) -> LLMGateway:
    return LLMGateway(transport, ROLES, registry, recorder)


def test_retryable_error_retries_same_model_when_role_allows(registry: PromptRegistry) -> None:
    roles = ROLES.model_copy(update={"roles": {"tutor": RoleConfig(model="m1", fallbacks=["m2"], retries=1)}})
    transport = FakeTransport(
        [TransportError("network", "blip", retryable=True), ok('{"answer": "4", "confidence": 0.9}')]
    )
    recorder = MemoryRecorder()
    result = LLMGateway(transport, roles, registry, recorder).structured(
        "tutor", "demo", {"question": "2+2"}, Answer, CTX
    )
    assert (result.model, result.fallback_used) == ("m1", False)
    assert [r.model for r in transport.requests] == ["m1", "m1"]
    assert [rec.status for rec in recorder.records] == ["error", "ok"]


def test_structured_success_records_telemetry(registry: PromptRegistry) -> None:
    t = FakeTransport([ok('{"answer": "x = 10", "confidence": 0.9}')])
    rec = MemoryRecorder()
    result = gateway(t, registry, rec).structured("tutor", "demo", {"question": "Solve"}, Answer, CTX)
    assert result.value.answer == "x = 10"
    assert result.prompt_version == "v1"
    assert len(rec.records) == 1 and rec.records[0].status == "ok"
    assert t.requests[0].provider == {"data_collection": "deny"}
    assert t.requests[0].response_format is not None
    assert "<question>Solve</question>" in t.requests[0].messages[1]["content"]


def test_fenced_json_is_accepted(registry: PromptRegistry) -> None:
    t = FakeTransport([ok('```json\n{"answer": "4", "confidence": 1}\n```')])
    assert (
        gateway(t, registry, MemoryRecorder()).structured("tutor", "demo", {"question": "q"}, Answer, CTX).value.answer
        == "4"
    )


def test_retryable_error_falls_back(registry: PromptRegistry) -> None:
    t = FakeTransport(
        [TransportError("timeout", "slow", retryable=True), ok('{"answer": "a", "confidence": 0.5}', "m2")]
    )
    rec = MemoryRecorder()
    result = gateway(t, registry, rec).structured("tutor", "demo", {"question": "q"}, Answer, CTX)
    assert result.fallback_used
    assert result.model == "m2"
    assert [r.status for r in rec.records] == ["error", "ok"]


def test_non_retryable_error_raises(registry: PromptRegistry) -> None:
    t = FakeTransport([TransportError("http_400", "bad", retryable=False)])
    with pytest.raises(LLMError) as exc:
        gateway(t, registry, MemoryRecorder()).text("tutor", "demo", {"question": "q"}, CTX)
    assert exc.value.code == "bad_request"


def test_out_of_credit_is_reported_without_fallback(registry: PromptRegistry) -> None:
    t = FakeTransport([TransportError("quota_exceeded", "402", retryable=False)])
    with pytest.raises(LLMError) as exc:
        gateway(t, registry, MemoryRecorder()).text("tutor", "demo", {"question": "q"}, CTX)
    assert exc.value.code == "quota_exceeded"
    assert len(t.requests) == 1  # no fallback model attempted


def test_all_models_fail(registry: PromptRegistry) -> None:
    t = FakeTransport([TransportError("http_503", "x", retryable=True), TransportError("timeout", "y", retryable=True)])
    with pytest.raises(LLMError) as exc:
        gateway(t, registry, MemoryRecorder()).text("tutor", "demo", {"question": "q"}, CTX)
    assert exc.value.code == "provider_error"


def test_invalid_output_repaired_once(registry: PromptRegistry) -> None:
    t = FakeTransport([ok('{"answer": 5}'), ok('{"answer": "5", "confidence": 0.7}')])
    result = gateway(t, registry, MemoryRecorder()).structured("tutor", "demo", {"question": "q"}, Answer, CTX)
    assert result.value.answer == "5"
    assert "did not match" in t.requests[1].messages[-1]["content"]


def test_invalid_output_twice_raises(registry: PromptRegistry) -> None:
    t = FakeTransport([ok("not json"), ok("still not json")])
    with pytest.raises(LLMError) as exc:
        gateway(t, registry, MemoryRecorder()).structured("tutor", "demo", {"question": "q"}, Answer, CTX)
    assert exc.value.code == "invalid_output"


def test_invalid_latex_escapes_are_fixed_without_a_repair_call(registry: PromptRegistry) -> None:
    t = FakeTransport([ok('{"answer": "$\\sqrt{2}$ and \\underline{x}", "confidence": 0.8}')])
    result = gateway(t, registry, MemoryRecorder()).structured("tutor", "demo", {"question": "q"}, Answer, CTX)
    assert result.value.answer == "$\\sqrt{2}$ and \\underline{x}"
    assert len(t.requests) == 1


def test_images_become_content_parts(registry: PromptRegistry) -> None:
    t = FakeTransport([ok("transcribed")])
    gateway(t, registry, MemoryRecorder()).text("tutor", "demo", {"question": "q"}, CTX, images=[ImageInput(b"png")])
    content = t.requests[0].messages[1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_embeddings_batched_and_dimension_checked(registry: PromptRegistry) -> None:
    rec = MemoryRecorder()
    vectors = gateway(FakeTransport([]), registry, rec).embed(["a", "b", "c"], CTX)
    assert len(vectors) == 3
    assert len(rec.records) == 2  # batch_size 2


def test_missing_prompt_variable(registry: PromptRegistry) -> None:
    with pytest.raises(PromptError):
        gateway(FakeTransport([]), registry, MemoryRecorder()).text("tutor", "demo", {}, CTX)


def test_prompt_file_requires_sections() -> None:
    with pytest.raises(PromptError):
        parse_prompt_file("---\nname: x\nversion: v1\nrole: tutor\n---\nno sections")


def test_repository_prompts_are_valid() -> None:
    roles = load_roles().roles
    reg = PromptRegistry()
    for folder in reg.root.iterdir():
        if folder.is_dir():
            prompt = reg.get(folder.name)
            assert prompt.role in roles, f"{prompt.name}: role {prompt.role!r} missing from roles.yaml"


class SpeechTransport(FakeTransport):
    def __init__(self, script: list[SpeechResponse | TransportError]) -> None:
        super().__init__([])
        self.speech_script = list(script)
        self.speech_calls: list[tuple[str, str, dict | None]] = []

    def speech(
        self, model: str, input_text: str, voice: str, timeout_s: float, provider: dict | None = None
    ) -> SpeechResponse:
        self.speech_calls.append((model, voice, provider))
        item = self.speech_script.pop(0)
        if isinstance(item, TransportError):
            raise item
        return item


VOICE_ROLES = ROLES.model_copy(
    update={"roles": {"voice": RoleConfig(model="kokoro", retries=1, usd_per_million_chars=0.62)}}
)


def test_speech_goes_through_the_gateway_recorded_and_priced(registry: PromptRegistry) -> None:
    """Read-aloud is a model call like any other: recorded in llm_call with its cost, sent with the provider
    preferences (no data collection), retried like the role says, and never silently empty."""
    t = SpeechTransport([TransportError("http_503", "busy", retryable=True), SpeechResponse(b"mp3", "DeepInfra", "g")])
    rec = MemoryRecorder()
    audio = LLMGateway(t, VOICE_ROLES, registry, rec).speech("voice", "x" * 1000, "bf_emma", CTX)
    assert audio == b"mp3"
    assert t.speech_calls == [("kokoro", "bf_emma", {"data_collection": "deny"})] * 2
    assert [(r.status, r.provider, r.prompt_name) for r in rec.records] == [
        ("error", None, "speech"),
        ("ok", "DeepInfra", "speech"),
    ]
    assert rec.records[-1].cost_usd == pytest.approx(0.00062)

    out_of_credit = SpeechTransport([TransportError("quota_exceeded", "402", retryable=False)])
    with pytest.raises(LLMError) as err:
        LLMGateway(out_of_credit, VOICE_ROLES, registry, MemoryRecorder()).speech("voice", "Hi.", "bf_emma", CTX)
    assert err.value.code == "quota_exceeded"
    empty = SpeechTransport([SpeechResponse(b"", "p", None)])
    with pytest.raises(LLMError):
        LLMGateway(empty, VOICE_ROLES, registry, MemoryRecorder()).speech("voice", "Hi.", "bf_emma", CTX)


class BatchFake(FakeTransport):
    """The Batch API, in memory: a submit is 'in_progress' until `finish` fills in the results."""

    def __init__(self) -> None:
        super().__init__([])
        self.submitted: list[tuple[str, list[dict]]] = []
        self.state: dict = {"status": "validating", "results": None}

    def submit_batch(self, model: str, requests: list[dict], timeout_s: float) -> dict:
        self.submitted.append((model, requests))
        return {"id": f"batch_{len(self.submitted)}", "status": "validating"}

    def get_batch(self, batch_id: str, timeout_s: float) -> dict:
        return self.state

    def finish(self, replies: dict[str, str | None]) -> None:
        results = []
        for custom_id, text in replies.items():
            if text is None:
                results.append({"custom_id": custom_id, "error": {"code": "provider_error", "message": "x"}})
            else:
                body = {
                    "choices": [{"message": {"content": text}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
                    "provider": "Fireworks",
                }
                results.append({"custom_id": custom_id, "response": {"status_code": 200, "body": body}})
        self.state = {"status": "completed", "results": results}


BATCH_ROLES = ROLES.model_copy(
    update={
        "roles": {
            "writer": RoleConfig(model="glm", batch_model="glm:batch", max_tokens=500),
            "tutor": RoleConfig(model="m1"),
        }
    }
)


def test_a_batch_runs_on_the_batch_variant_and_every_reply_is_checked_and_recorded(registry: PromptRegistry) -> None:
    """User rule (21 Sep 2026): batch jobs run on the role's `:batch` model through the Batch API. Each reply is
    validated against the schema and recorded with its cost; an unreadable one is a typed failure, not a guess."""
    t = BatchFake()
    rec = MemoryRecorder()
    gw = LLMGateway(t, BATCH_ROLES, registry, rec)
    items = [
        BatchItem("a", {"question": "1+1"}),
        BatchItem("b", {"question": "2+2"}),
        BatchItem("c", {"question": "x"}),
    ]
    handle = gw.batch_submit("writer", "demo", items, Answer, CTX)
    [(model, requests)] = t.submitted
    assert model == "glm:batch" and handle.custom_ids == ("a", "b", "c")
    assert requests[0]["body"]["response_format"]["type"] == "json_schema" and "stream" not in requests[0]["body"]

    assert gw.batch_collect(handle, Answer, CTX) is None  # still running
    t.finish({"a": '{"answer": "2", "confidence": 0.9}', "b": "not json", "c": None})
    outcome = gw.batch_collect(handle, Answer, CTX)
    assert outcome is not None and outcome.status == "completed"
    assert outcome.results["a"].value.answer == "2" and outcome.results["a"].model == "glm:batch"
    assert outcome.failures == {"b": "invalid_output", "c": "provider_error"}
    assert outcome.cost_usd == pytest.approx(0.0002)
    assert [(r.status, r.model) for r in rec.records] == [
        ("ok", "glm:batch"),
        ("ok", "glm:batch"),
        ("error", "glm:batch"),
    ]

    with pytest.raises(LLMError):  # a role with no batch variant is never silently run on something else
        gw.batch_submit("tutor", "demo", items, Answer, CTX)
