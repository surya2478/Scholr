"""The authenticated caller and service-layer permission checks (RLS is the second enforcement layer)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from app.core.errors import ApiError, forbidden

UserRole = Literal["student", "guardian", "admin"]


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    role: UserRole
    display_name: str
    mfa: bool
    student_id: UUID | None = None  # students only
    guardian_id: UUID | None = None  # guardians only
    # guardians only: active links, student_id -> granted scopes
    guardian_scopes: dict[UUID, frozenset[str]] = field(default_factory=dict)

    @property
    def visible_student_ids(self) -> list[UUID]:
        if self.role == "student" and self.student_id:
            return [self.student_id]
        if self.role == "guardian":
            return list(self.guardian_scopes)
        return []


def can_access_student(principal: Principal, student_id: UUID, scope: str | None = None) -> bool:
    if principal.role == "admin":
        return True
    if principal.role == "student":
        return principal.student_id == student_id
    scopes = principal.guardian_scopes.get(student_id)
    return scopes is not None and (scope is None or scope in scopes)


def require_student_access(principal: Principal, student_id: UUID, scope: str | None = None) -> None:
    if not can_access_student(principal, student_id, scope):
        raise forbidden(message="no access to this student's data")


def resolve_student_id(principal: Principal, requested: UUID | None, scope: str) -> UUID:
    """The student a request is about: defaults to the only visible student, otherwise must be given."""
    if requested is None:
        visible = principal.visible_student_ids
        if len(visible) != 1:
            raise ApiError(400, "student_id_required", "student_id is required for this account")
        requested = visible[0]
    require_student_access(principal, requested, scope)
    return requested


def require_role(principal: Principal, *roles: UserRole) -> None:
    if principal.role not in roles:
        raise forbidden(message="this action needs a different role")
