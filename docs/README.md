# Scholr Documentation — v2.1

| Doc | Purpose | Changes how often |
|---|---|---|
| [PRINCIPLES.md](PRINCIPLES.md) | Vision, rules, conflict resolution | Rarely |
| [CONTEXT.md](CONTEXT.md) | Student, school, subjects, exams, materials, unknowns | Each term |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data model, pipelines, API | Per phase |
| [PHASE-1.md](PHASE-1.md) | Current scope, plan, validation study, acceptance criteria | Weekly |
| [ROADMAP.md](ROADMAP.md) | Phases after Phase 1 | Per phase |
| [../CLAUDE.md](../CLAUDE.md) | Working instructions for the coding agent | As conventions settle |

Precedence when documents disagree: **PRINCIPLES > PHASE-1 > ARCHITECTURE > ROADMAP**. Raise the conflict; don't pick silently.

## Changelog: v2.0 → v2.1

**Structure**
- Single 80-section master prompt split into the documents above. Duplicated rules consolidated.

**Scope and sequencing**
- Phase 1 reduced to a thin vertical slice: **Maths 0580 Extended, then Sociology 0495** (instead of Maths + Physics + Chemistry). Physics follows the Phase 1 gate.
- Phase 1 timeline changed from "4–6 weeks" to ~14 weeks ending with the gate review before the end of Term 1 (December 2026), because retention checks need elapsed time.
- Sociology exam readiness pulled forward into Phase 2 (exam May/Jun 2027).

**Architecture**
- `learning_event` is the append-only source of truth; mastery, mistakes, memory are projections.
- Added `concept` (curriculum-neutral) and `concept_prerequisite` to support the IGCSE↔IIT bridge and gap tracing.
- Added `skill` as assessment objective / process skill (e.g. AO1–AO3), separate from content objectives.
- Added `teaching_plan_entry`, `commitment`, `school_result`, `upcoming_assessment`, `consent_record`, `llm_call`.
- Learning Engine and Evaluation implemented as **explicit state machines / bounded pipelines** with LLM steps, not open-ended agent loops. LangGraph, Redis, Celery deferred.
- Search pipeline (§16 in v2.0) now resolves path/subject/topic from session context first; classification only when ambiguous.
- Concrete, versioned **mastery rule v1**, help ladder L0–L5, and planner v1 algorithm.
- Handwritten maths answers: photo → vision transcription → student confirms → evaluation.

**Reliability**
- Generated maths questions must be SymPy-verified before being shown.
- Evaluations carry confidence; below threshold → review queue, no mastery update.
- Sociology evaluation uses dual-model marking with agreement check and calibration against teacher-marked work.
- Sociology outputs may not name studies, sociologists or statistics absent from retrieved sources unless labelled general knowledge.
- Student notes are low-authority for correctness.

**Evidence**
- North Star anchored to independent assessments (past-paper forms, school results), not the system's own mastery estimate.
- Validation uses within-student matched topic pairs (app vs normal study) with parallel test forms and crossover.

**Safety and privacy**
- Jurisdiction: UAE / India. Phase 1 treated as personal/domestic use; legal review required before platformization.
- Parent visibility: full access now, implemented as scoped grants so it can be restricted later. Student is told what parents can see.
- Pre-written (not LLM-generated) high-severity safety responses; verified crisis resources in config.
- Academic integrity rule for Cambridge-assessed coursework.
- OpenRouter configured to avoid providers that retain or train on data.
