"""Typed API errors with one response shape: {"error": {"code": ..., "message": ...}}."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.llm.gateway import LLMError


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def unauthorized(message: str = "authentication required") -> ApiError:
    return ApiError(401, "unauthorized", message)


def forbidden(code: str = "forbidden", message: str = "not allowed") -> ApiError:
    return ApiError(403, code, message)


def not_found(entity: str) -> ApiError:
    return ApiError(404, "not_found", f"{entity} not found")


def _body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status, headers=headers)

    @app.exception_handler(LLMError)
    async def _llm_error(request: Request, exc: LLMError) -> JSONResponse:
        # ARCHITECTURE §20: nothing partial is persisted; the student's work is already saved.
        code = "evaluation_failed" if exc.code == "invalid_output" else "llm_unavailable"
        message = "I'm having trouble right now — your work is saved. Please try again shortly."
        return JSONResponse(_body(code, message), status_code=503)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations only: validation messages can echo submitted values (answers, messages).
        fields = sorted({".".join(str(p) for p in err.get("loc", ())) for err in exc.errors()})
        body = {"error": {"code": "invalid_request", "message": "request failed validation", "fields": fields}}
        return JSONResponse(body, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)
