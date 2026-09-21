from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.safety import service
from app.modules.safety.schemas import IncidentOut, IncidentUpdate

router = APIRouter(tags=["safety"])


@router.get("/safety/incidents", response_model=list[IncidentOut])
def get_incidents(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    status: Literal["none", "notified", "acknowledged", "resolved"] | None = None,
) -> list[IncidentOut]:
    sid = resolve_student_id(principal, student_id, scope="safety")
    return service.list_incidents(s, principal, student_id=sid, status=status)


@router.patch("/safety/incidents/{incident_id}", response_model=IncidentOut)
def patch_incident(incident_id: UUID, body: IncidentUpdate, principal: PrincipalDep, s: DbDep) -> IncidentOut:
    return service.update_incident(s, principal, incident_id, body)
