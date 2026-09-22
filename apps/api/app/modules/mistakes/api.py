from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.mistakes import challenges, service
from app.modules.mistakes.challenges import BugChallenge, BugVerificationIn, BugVerificationOut
from app.modules.mistakes.schemas import MistakeOut

router = APIRouter(tags=["mistakes"])


@router.get("/mistakes", response_model=list[MistakeOut])
def get_mistakes(
    principal: PrincipalDep,
    s: DbDep,
    subject_id: UUID | None = None,
    status: Literal["open", "improving", "resolved"] | None = None,
    student_id: UUID | None = None,
) -> list[MistakeOut]:
    sid = resolve_student_id(principal, student_id, scope="progress")
    return service.list_mistakes(s, student_id=sid, subject_id=subject_id, status=status)


@router.get("/mistakes/challenges", response_model=list[BugChallenge])
def list_bug_challenges(principal: PrincipalDep, s: DbDep, subject_id: UUID | None = None) -> list[BugChallenge]:
    """Bug Hunter challenges, built from approved walkthroughs (mistakes/challenges.py)."""
    return challenges.list_challenges(s, subject_id=subject_id)


@router.post("/mistakes/challenges/{challenge_id}/verify", response_model=BugVerificationOut)
def verify_bug_challenge(
    challenge_id: str, submission: BugVerificationIn, principal: PrincipalDep, s: DbDep
) -> BugVerificationOut:
    """Mark her examiner's decision on a flawed solution."""
    return challenges.verify_challenge(s, challenge_id, submission)
