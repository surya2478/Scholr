from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.core.rbac import Principal, can_access_student, require_role, require_student_access


def principal(role: str, **kw: object) -> Principal:
    return Principal(user_id=uuid4(), tenant_id=uuid4(), role=role, display_name=role, mfa=True, **kw)  # type: ignore[arg-type]


def test_student_accesses_only_self() -> None:
    own, other = uuid4(), uuid4()
    p = principal("student", student_id=own)
    assert can_access_student(p, own)
    assert not can_access_student(p, other)
    assert p.visible_student_ids == [own]


def test_guardian_access_follows_links_and_scopes() -> None:
    linked, unlinked = uuid4(), uuid4()
    p = principal("guardian", guardian_id=uuid4(), guardian_scopes={linked: frozenset({"progress", "mastery"})})
    assert can_access_student(p, linked)
    assert can_access_student(p, linked, "mastery")
    assert not can_access_student(p, linked, "conversations")
    assert not can_access_student(p, unlinked)
    with pytest.raises(ApiError) as exc:
        require_student_access(p, linked, "conversations")
    assert exc.value.status == 403


def test_admin_and_role_checks() -> None:
    admin = principal("admin")
    assert can_access_student(admin, uuid4())
    require_role(admin, "admin")
    with pytest.raises(ApiError):
        require_role(principal("student", student_id=uuid4()), "admin", "guardian")
