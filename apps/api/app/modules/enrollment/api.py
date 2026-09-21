from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import require_student_access, resolve_student_id
from app.modules.enrollment import service
from app.modules.enrollment.schemas import (
    AvailabilityIn,
    AvailabilityOut,
    CommitmentIn,
    CommitmentOut,
    SchoolResultIn,
    SchoolResultOut,
    TeachingEntryIn,
    TeachingEntryOut,
    UpcomingIn,
    UpcomingOut,
)

router = APIRouter(tags=["enrollment"])
SCOPE = "plans"


def _week(values: dict[int, int]) -> AvailabilityOut:
    return AvailabilityOut(minutes=[values.get(day, 0) for day in range(7)])


@router.get("/students/{student_id}/availability", response_model=AvailabilityOut)
def get_availability(student_id: UUID, principal: PrincipalDep, s: DbDep) -> AvailabilityOut:
    require_student_access(principal, student_id, SCOPE)
    return _week(service.availability(s, student_id=student_id))


@router.put("/students/{student_id}/availability", response_model=AvailabilityOut)
def put_availability(student_id: UUID, body: AvailabilityIn, principal: PrincipalDep, s: DbDep) -> AvailabilityOut:
    require_student_access(principal, student_id, SCOPE)
    return _week(
        service.set_availability(s, tenant_id=principal.tenant_id, student_id=student_id, minutes=body.minutes)
    )


@router.get("/commitments", response_model=list[CommitmentOut])
def get_commitments(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[CommitmentOut]:
    return service.list_commitments(s, student_id=resolve_student_id(principal, student_id, SCOPE))


@router.post("/commitments", response_model=CommitmentOut, status_code=201)
def post_commitment(
    body: CommitmentIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> CommitmentOut:
    sid = resolve_student_id(principal, student_id, SCOPE)
    return service.add_commitment(s, tenant_id=principal.tenant_id, student_id=sid, body=body)


@router.delete("/commitments/{commitment_id}", status_code=204)
def remove_commitment(commitment_id: UUID, principal: PrincipalDep, s: DbDep) -> Response:
    require_student_access(principal, service.commitment_student(s, commitment_id), SCOPE)
    service.delete_commitment(s, commitment_id=commitment_id)
    return Response(status_code=204)


@router.get("/teaching-plan", response_model=list[TeachingEntryOut])
def get_teaching_plan(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[TeachingEntryOut]:
    return service.list_teaching_entries(s, student_id=resolve_student_id(principal, student_id, SCOPE))


@router.post("/teaching-plan", response_model=TeachingEntryOut, status_code=201)
def post_teaching_entry(
    body: TeachingEntryIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> TeachingEntryOut:
    sid = resolve_student_id(principal, student_id, SCOPE)
    return service.add_teaching_entry(s, tenant_id=principal.tenant_id, student_id=sid, body=body)


@router.delete("/teaching-plan/{entry_id}", status_code=204)
def remove_teaching_entry(entry_id: UUID, principal: PrincipalDep, s: DbDep) -> Response:
    require_student_access(principal, service.teaching_entry_student(s, entry_id), SCOPE)
    service.delete_teaching_entry(s, entry_id=entry_id)
    return Response(status_code=204)


@router.get("/upcoming-assessments", response_model=list[UpcomingOut])
def get_upcoming(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[UpcomingOut]:
    return service.list_upcoming_assessments(s, student_id=resolve_student_id(principal, student_id, SCOPE))


@router.post("/upcoming-assessments", response_model=UpcomingOut, status_code=201)
def post_upcoming(body: UpcomingIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> UpcomingOut:
    sid = resolve_student_id(principal, student_id, SCOPE)
    return service.add_upcoming_assessment(s, tenant_id=principal.tenant_id, student_id=sid, body=body)


@router.delete("/upcoming-assessments/{upcoming_id}", status_code=204)
def remove_upcoming(upcoming_id: UUID, principal: PrincipalDep, s: DbDep) -> Response:
    require_student_access(principal, service.upcoming_student(s, upcoming_id), SCOPE)
    service.delete_upcoming_assessment(s, upcoming_id=upcoming_id)
    return Response(status_code=204)


@router.post("/school-results", response_model=SchoolResultOut, status_code=201)
def post_school_result(
    body: SchoolResultIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> SchoolResultOut:
    sid = resolve_student_id(principal, student_id, "progress")
    return service.record_school_result(
        s, tenant_id=principal.tenant_id, student_id=sid, body=body, now=datetime.now(UTC)
    )
