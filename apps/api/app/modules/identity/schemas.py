from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    id: UUID
    display_name: str
    role: str


class EnrollmentOut(BaseModel):
    subject_id: UUID
    subject_code: str
    subject_name: str
    tier: str | None
    exam_session: str | None
    answer_input: str = "text"  # from the subject config: "expression" offers the maths keyboard
    stage: str = "taught"  # from the subject config: only "taught" subjects have questions to set


class StudentOut(BaseModel):
    id: UUID
    display_name: str
    year_group: str
    timezone: str
    enrollments: list[EnrollmentOut] = Field(default_factory=list)


class LinkedStudentOut(StudentOut):
    scopes: list[str]


class GuardianVisibilityOut(BaseModel):
    """What a linked guardian can see — shown to the student (ARCHITECTURE §18)."""

    guardian_name: str
    scopes: list[str]


class MeOut(BaseModel):
    user: UserOut
    student: StudentOut | None = None
    guardian_visibility: list[GuardianVisibilityOut] = Field(default_factory=list)
    linked_students: list[LinkedStudentOut] = Field(default_factory=list)


class DevSessionIn(BaseModel):
    """Development sign-in: pick which seeded household account to use."""

    model_config = ConfigDict(extra="forbid")
    role: Literal["student", "guardian"] = "student"


class DevSessionOut(BaseModel):
    token: str
    role: str
    display_name: str


class RegisterIn(BaseModel):
    """Self-service registration (docs/STUDENT-APP.md D7). The account stays pending until an admin approves."""

    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=200)
    requested_streams: list[str] = Field(default_factory=list, max_length=8)
    note: str = Field(default="", max_length=500)


class RegisterOut(BaseModel):
    status: Literal["pending"] = "pending"
    message: str


class SignInIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class SignInOut(BaseModel):
    token: str
    role: str
    display_name: str
    expires_in_hours: float


class StreamChoiceOut(BaseModel):
    """A stream a registration may ask for, as the sign-up form shows it."""

    key: str
    name: str
    status: str


class PendingAccountOut(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    requested_streams: list[str]
    note: str
    requested_at: datetime


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["student", "guardian", "admin"] = "student"
    streams: list[str] = Field(default_factory=list, max_length=8)
    year_group: str = Field(default="", max_length=32)
    timezone: str = Field(default="Asia/Dubai", max_length=64)


class ApproveOut(BaseModel):
    user_id: UUID
    role: str
    streams: list[str]
    subjects_enrolled: list[str]


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="", max_length=500)
