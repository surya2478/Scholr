from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.deps import PrincipalDep, SessionsDep, llm_gateway
from app.core.telemetry import request_id_of
from app.llm.gateway import CallContext
from app.modules.routing import service
from app.modules.routing.schemas import RouteIn, RouteOut

router = APIRouter(tags=["routing"])


@router.post("/route", response_model=RouteOut)
def post_route(body: RouteIn, request: Request, principal: PrincipalDep, sessions: SessionsDep) -> RouteOut:
    ctx = CallContext(request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=principal.student_id)
    return service.route(sessions, lambda: llm_gateway(request), ctx, principal, body)
