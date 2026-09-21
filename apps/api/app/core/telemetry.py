"""Request correlation. Logs carry the request id, never conversation text or answers."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.core.ids import uuid7

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")


def install_request_id(app: FastAPI) -> None:
    @app.middleware("http")
    async def _request_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else str(uuid7())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "") or str(uuid7())
