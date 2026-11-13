from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SubjectProgressOut(BaseModel):
    subject_id: UUID
    subject_name: str
    objectives_total: int
    level_counts: dict[str, int]  # level name -> objectives; empty when the caller cannot see mastery
    competent_or_better: int
    retention_high: int
    open_mistakes: int
    high_severity_mistakes: int


class WeekOut(BaseModel):
    since: date
    attempts_evaluated: int
    answers_without_help: int  # marked answers reached with at most a nudge (help level <= 1)
    mistakes_fixed: int
    study_minutes: int
    active_days: int
    plan_items_total: int
    plan_items_completed: int
    plan_items_skipped: int


class FocusOut(BaseModel):
    kind: Literal["mistake", "retention"]
    subject_id: UUID
    objective_id: UUID | None
    objective_code: str | None
    label: str


class WinOut(BaseModel):
    subject_id: UUID
    objective_id: UUID
    objective_code: str
    objective_statement: str
    level_name: str
    last_demonstrated_at: datetime


class ProgressSummaryOut(BaseModel):
    student_id: UUID
    generated_at: datetime
    subjects: list[SubjectProgressOut]
    week: WeekOut
    focus: list[FocusOut]
    recent_wins: list[WinOut]


class SafetyOverviewOut(BaseModel):
    open_total: int
    open_by_severity: dict[str, int]
    latest_open_at: datetime | None


class UpcomingBriefOut(BaseModel):
    subject_id: UUID
    subject_name: str
    title: str
    due_at: datetime
    objectives_total: int
    objectives_secure: int | None  # None without the `mastery` scope
    notes: str | None


class SuggestionOut(BaseModel):
    """One plain-language suggestion for the guardian, from stored progress (no LLM)."""

    lead: str
    text: str


class GuardianOverviewOut(BaseModel):
    student_id: UUID
    student_name: str
    scopes: list[str]  # what this guardian can see; the student is shown the same list (PRINCIPLES 26)
    summary: ProgressSummaryOut
    evaluations_needing_review: int | None  # None without the `assessments` scope
    upcoming_assessments: list[UpcomingBriefOut] | None  # None without the `plans` scope
    safety: SafetyOverviewOut | None  # None without the `safety` scope
    suggestions: list[SuggestionOut]


class MonthSubjectOut(BaseModel):
    subject_id: UUID
    subject_name: str
    answers_marked: int
    marks_awarded: float  # settled marks only (final or reviewed)
    marks_available: float
    accuracy: float | None  # marks_awarded / marks_available; None when nothing settled
    independent_share: float | None  # share of marked answers given with at most a nudge (help level <= 1)
    awaiting_review: int
    sessions: int
    study_minutes: int
    mistakes_found: int
    mistakes_resolved: int
    topics_secured: int | None  # None without the `mastery` scope


class MonthTotalsOut(BaseModel):
    answers_marked: int
    accuracy: float | None
    active_days: int
    study_minutes: int


class MonthlySummaryOut(BaseModel):
    """Guardian monthly summary (PHASE-1 W12). Derived from events, mastery and plans; no LLM writes it."""

    student_id: UUID
    student_name: str
    month: str  # YYYY-MM in the student's timezone
    previous_month: str
    next_month: str | None  # None while the next month has not started
    days_counted: int  # days of the month up to today
    totals: MonthTotalsOut
    previous: MonthTotalsOut
    subjects: list[MonthSubjectOut]
    plan_items_total: int | None  # None without the `plans` scope
    plan_items_completed: int | None
    plan_items_skipped: int | None
    secured: list[WinOut] | None  # topics last shown at competent or better this month; None without `mastery`
    focus: list[FocusOut] | None  # current recurring mistakes and fading topics; only for the current month


class TrendWeekOut(BaseModel):
    week_start: date
    topics_secure: int | None  # None without the `mastery` scope
    answers_marked: int
    without_help: int  # help level 0-1
    with_hints: int  # help level 2-4
    worked_solution: int  # help level 5
    independent_share: float | None


class TrendDayOut(BaseModel):
    day: date
    study_minutes: int


class TrendSubjectOut(BaseModel):
    subject_id: UUID
    subject_name: str
    study_minutes: int


class TrendsOut(BaseModel):
    """Weekly series behind the guardian charts. Replayed from events; no LLM, nothing stored."""

    student_id: UUID
    weeks: list[TrendWeekOut]
    days: list[TrendDayOut]  # the current week, Monday to Sunday
    subjects: list[TrendSubjectOut]  # study minutes over the weeks shown
    planned_minutes_per_day: int  # the family's own availability, for comparison


class MetacognitionItem(BaseModel):
    attempt_id: UUID
    subject_id: UUID
    question_stem: str
    pre_confidence: int
    confidence_label: str
    marks_awarded: float
    marks_available: float
    percentage: int
    quadrant: Literal["true_mastery", "dangerous_blindspot", "hesitant_mastery", "known_gap"]
    mistakes: list[str]
    submitted_at: datetime
    time_spent_s: int | None = None
    velocity_category: Literal["optimal_flow", "speed_trap", "time_sink", "hesitant_success", "untracked"] = "untracked"


class QuadrantCount(BaseModel):
    count: int
    percentage: float


class VelocityQuadrant(BaseModel):
    count: int
    percentage: float


class VelocityStats(BaseModel):
    speed_trap_count: int
    time_sink_count: int
    optimal_flow_count: int
    hesitant_count: int
    average_seconds_per_mark: float
    # Her time against the time her papers allow for the same marks (100 = exactly exam pace); None if untimed.
    exam_time_used_percent: int | None = None
    quadrants: dict[str, VelocityQuadrant]
    diagnosis: str


class IndependenceStats(BaseModel):
    independence_index: float  # 0.0 to 100.0%
    tier: str  # Silent Master, Self-Reliant, Guided Explorer, Supported Apprentice
    unassisted_count: int  # help level 0
    nudged_count: int  # help level 1
    assisted_count: int  # help level >= 2
    total: int
    advice: str


class MetacognitionOut(BaseModel):
    student_id: UUID
    total_evaluated_with_confidence: int
    brier_calibration_score: float | None  # 0.0 to 100.0; None until MIN_CALIBRATION_ANSWERS rated answers
    calibration_rating: str
    quadrants: dict[str, QuadrantCount]
    blindspots: list[MetacognitionItem]
    recent_items: list[MetacognitionItem]
    advice: str
    independence: IndependenceStats
    velocity: VelocityStats | None = None
