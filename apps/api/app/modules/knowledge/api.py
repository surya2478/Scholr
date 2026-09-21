from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.deps import DbDep, PrincipalDep, SettingsDep, llm_gateway
from app.core.errors import forbidden
from app.core.telemetry import request_id_of
from app.llm.gateway import CallContext
from app.modules.knowledge import service
from app.modules.knowledge.schemas import RetrievedChunkOut, SearchRequest, SearchResponse

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/search", response_model=SearchResponse)
def debug_search(
    body: SearchRequest, request: Request, principal: PrincipalDep, s: DbDep, settings: SettingsDep
) -> SearchResponse:
    """Retrieval debugging (ARCHITECTURE §24). Admin only in production; returns short excerpts only."""
    if settings.app_env == "prod" and principal.role != "admin":
        raise forbidden(message="retrieval debugging is restricted to admins")
    ctx = CallContext(
        request_id=request_id_of(request),
        tenant_id=principal.tenant_id,
        student_id=principal.student_id,
    )
    result = service.search(
        s,
        llm_gateway(request),
        ctx,
        query=body.query,
        subject_id=body.subject_id,
        objective_ids=body.objective_ids,
        k=body.k,
    )
    return SearchResponse(
        state=result.state,
        chunks=[
            RetrievedChunkOut(
                id=c.id,
                source_title=c.source_title,
                printed_page=c.printed_page,
                heading_path=c.heading_path,
                content_kind=c.content_kind,
                authority_tier=c.authority_tier,
                excerpt=c.content[: service.EXCERPT_CHARS],
                similarity=c.similarity,
                aligned=c.aligned,
            )
            for c in result.chunks
        ],
    )
