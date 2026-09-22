"""OpenRouter transport: the Batch API calls (docs/STUDENT-APP.md §17)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.llm.transport import OpenRouterTransport, TransportError


def transport(handler) -> OpenRouterTransport:  # type: ignore[no-untyped-def]
    return OpenRouterTransport(
        "key", "https://openrouter.test/api/v1", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_an_accepted_batch_is_not_mistaken_for_an_error() -> None:
    """A batch object always carries "error": null. Reading that as a failure once left a submitted batch running
    unrecorded (21 Sep 2026)."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(202, json={"id": "batch_1", "status": "validating", "error": None, "results": None})

    data = transport(handler).submit_batch("z-ai/glm-5.3-flash:batch", [{"custom_id": "a", "body": {}}])
    assert data["id"] == "batch_1"
    assert list(seen[0]) == ["endpoint", "model", "requests"]  # requests last: the API stream-parses the body


def test_a_real_error_still_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 400, "message": "bad model"}})

    with pytest.raises(TransportError):
        transport(handler).submit_batch("nope", [{"custom_id": "a", "body": {}}])
