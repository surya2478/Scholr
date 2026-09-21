# Architecture — v2.1

Status legend: **Decided** · **Default** (use unless evidence says otherwise) · **Open** (decide by the week noted).

## 1. System shape

```
                         STUDENT / PARENT UI (Next.js PWA)
                                      │  REST + SSE
                                      ▼
┌────────────────────────── FastAPI modular monolith ──────────────────────────┐
│                                                                              │
│  Safety gate (every input & output) ─────────────────────────────┐           │
│         │                                                        │           │
│  Master Router (context-first) ──► Path Orchestrator (thin)      │           │
│         │                                  │                     │           │
│         ▼                                  ▼                     │           │
│  Subject Expertise Engine  ◄── subject_configs/*.yaml            │           │
│         │                                                        │           │
│   ┌─────┴───────────┬──────────────────┬──────────────────┐      │           │
│   ▼                 ▼                  ▼                  ▼      │           │
│ Learning Engine  Assessment        Evaluation         Knowledge  │           │
│ (state machine)  (select+generate) (bounded pipeline)  (RAG)     │           │
│   │                 │                  │                         │           │
│   └────────────── emits ───────────────┘                         │           │
│                     ▼                                            │           │
│              learning_event (append-only)                        │           │
│                     │ projections                                │           │
│        ┌────────────┼──────────────┬──────────────┐              │           │
│        ▼            ▼              ▼              ▼              │           │
│     Mastery     Mistake Bank   Learning Memory  Progress         │           │
│        └────────────┴──────┬───────┘                             │           │
│                            ▼                                     │           │
│                     Planner ──► My Day                           │           │
│                                                                  │           │
│  LLM Gateway (OpenRouter) · Deterministic tools · Audit · Telemetry ◄────────┘
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                    PostgreSQL 16 + pgvector + FTS · private object storage
```

## 2. Component classification (authoritative)

| Component | Implementation | Phase |
|---|---|---|
| Master Router | Deterministic from session context; LLM classifier only when ambiguous | 1 |
| Path Orchestrators | Thin deterministic dispatch (IGCSE now; IIT, India later) | 1 |
| Subject Expertise Engine | Config loader + narrow LLM steps parameterized by config | 1 |
| Learning Engine | **Explicit state machine**; LLM for diagnosis and response composition; bounded tool/retrieval calls | 1 |
| Socratic Critic | A step inside the Learning Engine's feedback state | 1 |
| Assessment | Deterministic selection; question bank first; LLM wording with verification | 1 |
| Evaluation | **Bounded pipeline** per subject type; deterministic tools + LLM rubric marking + agreement check | 1 |
| Mastery Engine | Deterministic projection, versioned rules | 1 |
| Mistake Bank | Deterministic projection from diagnosed mistakes | 1 |
| Learning Memory | Deterministic storage; LLM summarizes sessions into structured, evidence-linked statements | 1 |
| Planner | Deterministic priority + capacity fill; templated reasons | 1 (v1) |
| Progress Reviewer | Deterministic aggregation; optional LLM narrative | 1 (basic) |
| Safety Layer | Rules → classifier → policy table → escalation | 1 |
| Audit Log | Deterministic | 1 |
| Study Critic | Rule-based pattern detection over events + LLM phrasing | 2 |
| Supportive Companion | Agentic, high guardrails | 2 (limited), 5 |
| Career Guide | Agentic | 5 |
| Career Radar | Scheduled batch synthesis every 6–12 months | 5 |

"Modes" (Teacher, Practice Coach, Examiner, …) are UI experiences over these components. The student sees at most: **Learn · Practice · Test**.

## 3. Module layout

```
apps/api/app/
  core/            config, db session, auth (JWT verify), rbac, telemetry, errors, ids
  llm/             gateway.py, openrouter.py, roles.yaml, prompts/<name>/<version>.md, schemas/
  tools/           math_sympy.py, numeric.py, units.py (Pint), scoring.py, dates.py
  modules/
    identity/      users, students, guardians, links, consent
    curriculum/    curriculum, syllabus, subject, topic tree, objectives, skills, concepts
    enrollment/    enrollments, teaching plan, commitments, school results, upcoming assessments
    knowledge/     sources, ingestion, chunking, embedding, retrieval, validation
    subjects/      expertise engine, config schema, config loader
    routing/       router, path orchestrators
    tutoring/      learning engine state machine, sessions, conversations
    assessment/    question bank, templates, generation, verification, assessments
    evaluation/    pipelines (numeric, structured-math, essay), review queue
    events/        learning_event append + projection dispatcher
    mastery/       mastery + skill-profile projections, retention job
    mistakes/      mistake patterns projection
    memory/        learning memory
    planner/       daily plan
    progress/      student + parent summaries
    safety/        rules, classifier, policy, incidents, notifications
    audit/         audit log
    studies/       validation study: topic assignment, forms, schedule, analysis
  jobs/            scheduler + job definitions
apps/api/subject_configs/   igcse_maths_0580.yaml, igcse_sociology_0495.yaml, _schema.md
evals/                      datasets/<subject>/, runners/, reports/
```

Dependency rule: `api → service → repository`; cross-module calls only via `service`. `events` is the only module other modules write learning facts to.

## 4. Technology decisions

| Area | Choice | Status |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, uv | Decided |
| Frontend | Next.js App Router, TypeScript, Tailwind, KaTeX, MathLive, PWA | Decided |
| DB | PostgreSQL 16, pgvector (HNSW), `tsvector` FTS, RLS | Decided |
| Jobs | Postgres-backed scheduler (e.g. procrastinate or APScheduler with DB job store) | Default |
| Redis / Celery / LangGraph | Not in Phase 1 | Decided |
| LLM access | OpenRouter (OpenAI-compatible API) behind `LLMGateway` | Decided |
| LLM privacy | OpenRouter account + request settings that exclude providers which train on or retain prompts (verify current settings names) | Decided |
| Model assignment | By role in `llm/roles.yaml`; chosen by eval results (see §19) | Default |
| Embeddings | Multilingual model (English now, Arabic later). Via OpenRouter if supported, else local `bge-m3`. Pick by retrieval eval in W2 | Open (W2) |
| Reranking | Start: hybrid RRF + cross-encoder (e.g. `bge-reranker-v2-m3`) or LLM rerank. Keep only if it improves retrieval eval | Open (W2) |
| Auth | Managed provider issuing JWTs (default candidate: Clerk); FastAPI verifies JWKS; roles and grants live in our DB. Confirm provider terms allow a 15-year-old user | Open (W0) |
| Object storage | Private S3-compatible bucket, server-side encryption, signed URLs | Default |
| Hosting | Single region near UAE/India; managed Postgres with daily backups | Open (W5, U6) |
| Observability | OpenTelemetry traces + structured JSON logs + `llm_call` table; optional self-hosted Langfuse | Default |
| Maths tools | SymPy (parsing, equivalence, solving), custom sig-fig/tolerance validator | Decided |
| Handwriting | Vision-capable model via gateway role `vision_transcriber` | Decided |

## 5. Data model

All student-data tables carry `tenant_id` and `student_id` with RLS. UUID v7 primary keys. `created_at`/`updated_at` on every table.

### 5.1 Identity & access
| Table | Key columns |
|---|---|
| `tenant` | id, name |
| `app_user` | id, tenant_id, auth_subject, email, role (`student`/`guardian`/`admin`), status |
| `student` | id, user_id, display_name, year_group, timezone, locale |
| `guardian` | id, user_id |
| `guardian_student_link` | guardian_id, student_id, scopes `text[]`, granted_by, granted_at, revoked_at |
| `consent_record` | id, student_id, user_id, kind (`guardian_consent`/`student_assent`), policy_version, granted_at, withdrawn_at |

Scopes: `progress`, `mastery`, `assessments`, `plans`, `conversations`, `safety`, `memory`. Phase 1 grants all.

### 5.2 Curriculum
| Table | Key columns |
|---|---|
| `curriculum` | id, code (`CAIE-IGCSE`), name |
| `path` | id, code (`IGCSE`/`IIT`/`INDIA`), name |
| `syllabus` | id, curriculum_id, code (`0580`), title, version, first_exam_year, last_exam_year, tiers |
| `exam_component` | id, syllabus_id, code (`P2`), name, tier, duration_min, marks, calculator_allowed |
| `subject` | id, path_id, syllabus_id?, code (`igcse-maths`), name, config_key |
| `topic` / `subtopic` | id, parent_id, code, name, position, syllabus_ref |
| `learning_objective` | id, subtopic_id, code, statement, tier (`core`/`extended`/`all`), syllabus_ref |
| `skill` | id, subject_id?, code (`AO2`), name, kind (`assessment_objective`/`process`) |
| `concept` | id, name, description — curriculum-neutral |
| `objective_concept` | objective_id, concept_id |
| `concept_prerequisite` | concept_id, prerequisite_id, strength |

`concept` is how IGCSE and IIT share knowledge: both curricula's objectives map to the same concept, each with its own depth, questions and mastery.

### 5.3 Enrollment & schedule
| Table | Key columns |
|---|---|
| `enrollment` | id, student_id, subject_id, tier, exam_session (`2028-06`), status |
| `teaching_plan_entry` | id, student_id, subject_id, term, starts_on, ends_on, topic_ids, source |
| `commitment` | id, student_id, kind (`iit_class`/`extracurricular`/`other`), rrule, duration_min |
| `availability` | id, student_id, weekday, minutes |
| `upcoming_assessment` | id, student_id, subject_id, due_on, title, objective_ids |
| `school_result` | id, student_id, subject_id, assessed_on, title, score, max_score, objective_ids, notes |

### 5.4 Knowledge
| Table | Key columns |
|---|---|
| `source` | id, title, publisher, edition, owner, licence, authority_tier, acquired_via, private, subject_id, curriculum_id, version, ingestion_status, ingested_at |
| `knowledge_document` | id, source_id, storage_uri, content_type, language, page_count, checksum |
| `knowledge_chunk` | id, document_id, subject_id, topic_id, objective_ids, content_kind, difficulty, page_ref, content, embedding `vector`, tsv `tsvector`, metadata `jsonb` |
| `retrieval_log` | id, request_id, query, filters, candidates, state, created_at |

`content_kind`: `syllabus`, `explanation`, `definition`, `worked_example`, `question`, `mark_scheme`, `examiner_report`, `school_material`, `student_note`.

### 5.5 Assessment & evaluation
| Table | Key columns |
|---|---|
| `question_item` | id, subject_id, origin (`past_paper`/`textbook`/`school`/`template`/`generated`), source_id?, stem, parts `jsonb`, marks, command_word, objective_ids, skill_ids, difficulty, calculator_allowed, answer_spec `jsonb`, mark_scheme `jsonb`, verification_status, reserved_for_study, generator_version |
| `assessment` | id, student_id, subject_id, kind (`practice`/`quiz`/`baseline`/`post`/`retention`/`exam_style`), form_code, status, selection_rule_version, config, submitted_at |
| `assessment_item` | assessment_id, question_item_id, position |
| `attempt` | id, student_id, question_item_id, assessment_id?, session_id?, answer_text, answer_image_uris, transcription, transcription_confirmed_at, pre_confidence (1–4), max_assistance_level (0–5), time_spent_s, submitted_at |
| `evaluation` | id, attempt_id, pipeline, pipeline_version, rubric_version, marks_awarded, marks_available, criterion_scores `jsonb`, level_band, feedback `jsonb`, diagnosed_mistakes `jsonb`, tool_results `jsonb`, confidence, agreement `jsonb`, status (`final`/`needs_review`/`overridden`), reviewed_by |

### 5.6 Learning
| Table | Key columns |
|---|---|
| `learning_session` | id, student_id, subject_id, objective_id?, mode, started_at, ended_at, active_minutes |
| `conversation` / `message` | id, session_id, role, content, assistance_level, retrieval_state, safety_status |
| `learning_event` | id, student_id, occurred_at, type, subject_id, objective_ids, payload `jsonb`, schema_version, ref_type, ref_id — **append-only** (no UPDATE/DELETE grants) |
| `mastery_state` | student_id, objective_id, level, score, mastery_confidence, evidence_count, independent_successes, last_demonstrated_at, retention_risk, rule_version |
| `skill_profile` | student_id, subject_id, skill_id, score, evidence_count, rule_version |
| `mistake_pattern` | id, student_id, subject_id, topic_id, objective_id, mistake_type, description, occurrences, severity, first_seen, last_seen, status, resolution |
| `mistake_occurrence` | id, pattern_id, attempt_id, evaluation_id, occurred_at |
| `learning_memory` | id, student_id, subject_id?, kind (`strength`/`difficulty`/`misconception`/`preference`/`note`), statement, evidence_event_ids, status, superseded_by |

Event types (Phase 1): `session_started`, `session_ended`, `explanation_viewed`, `attempt_submitted`, `attempt_evaluated`, `evaluation_overridden`, `help_requested`, `help_given` (with level), `self_explanation_given`, `confidence_reported`, `mistake_diagnosed`, `mistake_resolved`, `school_result_recorded`, `plan_item_completed`, `plan_item_skipped`.

### 5.7 Planning
| Table | Key columns |
|---|---|
| `goal` | id, student_id, kind, statement, target_date, status |
| `study_plan` | id, student_id, plan_date, generator_version, inputs_snapshot `jsonb` |
| `plan_item` | id, plan_id, kind (`school_topic`/`revision`/`mistake_fix`/`practice`/`challenge`/`assessment`), objective_id, est_minutes, priority, reason_code, status |

### 5.8 Governance & telemetry
| Table | Key columns |
|---|---|
| `audit_log` | id, actor_user_id, action, entity_type, entity_id, metadata, ip, created_at — no conversation text |
| `safety_incident` | id, student_id, message_id, occurred_at, category, severity, rule_hits, classifier_output, policy_version, action_taken, escalation_status, notified_at, resolved_at, notes |
| `llm_call` | id, request_id, role, model, provider, prompt_name, prompt_version, input_tokens, output_tokens, cost_usd, latency_ms, status, fallback_used, error_code |
| `study_assignment` | id, student_id, subject_id, objective_ids, arm (`app`/`control`), pair_code, assigned_at, crossover_at |

### 5.9 Designed now, created in later phases
`achievement`, `extracurricular_activity`, `project`, `career_interest`, `career_radar_report`, `external_training_log` (IIT), `journey_edge`.

## 6. Request flow: a tutoring turn

```
POST /tutor/sessions/{id}/turns
  1. auth + RBAC (student owns session)
  2. safety.check_input(text)            → may short-circuit with policy response
  3. routing.resolve(session, text)       → {path, subject, objective, intent}
  4. subjects.load_config(subject)
  5. tutoring.engine.step(state, input)   → state machine transition
       ├─ knowledge.retrieve(...)          (≤1 per turn)
       ├─ tools.* (sympy etc.)             (≤3 per turn)
       └─ llm.gateway(role=tutor, prompt, schema)
  6. safety.check_output(response)
  7. events.append(...) → projections updated (sync for mastery; async for memory)
  8. persist message; stream response (SSE)
```

Latency target: first token ≤ 2 s, complete turn ≤ 8 s (p90). Evaluation of handwritten work may take longer and shows progress.

## 7. Master Router

Resolution order — stop at the first that yields a confident result:

1. **Active assessment lock** — inside an assessment, all input belongs to it (no tutoring help in `baseline`/`post`/`retention`).
2. **Session context** — session's subject/objective from the UI.
3. **Rules** — keyword/syllabus-term index restricted to the student's enrollments.
4. **LLM classifier** (role `classifier`, structured output with confidence) — only if 1–3 fail or conflict.
5. **Ask the student** — if classifier confidence < threshold, offer 2–3 choices.

Intents (Phase 1): `explain`, `practice`, `help_on_attempt`, `check_answer`, `plan`, `progress`, `off_topic`, `wellbeing`. `wellbeing` goes to the safety policy's supportive response in Phase 1 (no companion yet).

## 8. Subject Expertise Engine

One engine, many configs. Config schema (Pydantic-validated YAML):

```yaml
key: igcse_maths_0580
path: IGCSE
subject_code: igcse-maths
syllabus: { code: "0580", tier: extended, exam_session: "2028-06" }
subject_type: quantitative          # quantitative | essay | language | mixed
retrieval:
  allowed_authority_tiers: [A, B, C, D]
  related_subjects: []              # Phase 1: none
  grounding_critical_intents: [syllabus_scope, notation, exam_technique]
pedagogy:
  help_ladder: default
  self_explanation_every_n_correct: 3
  worked_example_style: step_by_step
question_types: [short_numeric, structured_multi_part, algebraic_expression, show_that]
question_sources: [past_paper, textbook, template, generated_verified]
difficulty_model: { scale: 1-5, anchors: { 3: "Paper 2/4 mid-paper item" } }
evaluation:
  pipeline: structured_math
  criteria: [concept, method, reasoning, accuracy, final_answer]
  mark_scheme_notation: [M, A, B, FT, oe, cao, isw]
  accuracy_rules: { default_sig_figs: 3, angle_dp: 1 }
  confidence_threshold: 0.75
common_mistakes: [sign_error, order_of_operations, misread_question, wrong_formula,
                  premature_rounding, word_problem_translation, units_omitted]
mastery_rules: default_v1
tools: [sympy_equivalence, sympy_solve, sig_fig_check]
calculator_modes: { P2: false, P4: true }
language: en
```

```yaml
key: igcse_sociology_0495
path: IGCSE
subject_code: igcse-sociology
syllabus: { code: "0495", tier: none, exam_session: "2027-06" }
subject_type: essay
retrieval:
  allowed_authority_tiers: [A, B, C]           # student notes excluded from grounding
  citation_required_for: [named_study, sociologist, statistic, definition]
pedagogy:
  help_ladder: essay
  socratic_prompts: [evidence, counterargument, application_to_example]
question_types: [define, identify, describe, explain, discuss, to_what_extent]
question_sources: [past_paper, textbook, school, generated_format_checked]
evaluation:
  pipeline: essay_levels
  criteria: { AO1: knowledge_understanding, AO2: interpretation_application, AO3: analysis_evaluation }
  level_descriptors_source: mark_scheme
  dual_marking: true
  max_disagreement: { short_answer_marks: 1, essay_levels: 0 }
  confidence_threshold: 0.8
common_mistakes: [description_not_explanation, no_evidence, one_sided, no_counterargument,
                  concept_misdefined, not_answering_command_word, generic_example]
mastery_rules: default_v1
tools: [word_count, command_word_check]
language: en
```

Rule: if engine code needs to branch on a subject, add a config field.

## 9. Knowledge & RAG

### 9.1 Authority tiers
| Tier | Sources | Used for |
|---|---|---|
| A | Cambridge syllabus, mark schemes, examiner reports | Scope, marking, exam technique |
| B | Course textbooks (Collins Maths, Sociology textbook) | Explanations, examples |
| C | School PPTs, worksheets | Explanations, school alignment |
| D | Student notes | Personalization only; not grounding for correctness |
| E | General reference | Labelled general knowledge |

### 9.2 Ingestion
```
manifest (content/manifests/*.yaml: owner, licence, tier, edition)
  → upload to private storage → extract (PDF text; OCR/vision for scans)
  → structure-aware chunking (headings, worked examples and Q+MS kept whole)
  → objective tagging (rules from syllabus refs + LLM tagger + human spot-check)
  → embed + tsvector → ingestion report → audit_log
```
Past-paper questions are additionally parsed into `question_item` rows with their mark schemes; items reserved for the validation study are flagged `reserved_for_study` and excluded from practice.

### 9.3 Retrieval
```
filters: tenant, subject ∈ allowed, tier ≥ subject minimum, objective/topic (if known)
  → vector top-30 ∪ FTS top-30 → reciprocal rank fusion
  → rerank to top-8 → validation → state
```
Scope expansion if too few candidates: objective → topic → subject → general reference (labelled). Phase 1 never retrieves across subjects.

### 9.4 Context validation → state
Deterministic checks: subject/objective alignment from metadata, authority tier, rerank score, number of independent supporting chunks, content_kind fit for intent. LLM check (role `grounding_check`) only for grounding-critical intents: evidence coverage and contradiction.

| State | Initial rule (calibrate on eval set in W2) |
|---|---|
| `HIGH` | ≥2 aligned chunks, tier A–C, rerank ≥ t_high, coverage = full, no contradiction |
| `MEDIUM` | ≥1 aligned chunk, tier A–C, rerank ≥ t_med, coverage ≥ partial |
| `LOW` | only topic-level or tier E matches, or partial coverage below t_med |
| `NONE` | nothing passes filters, or contradiction unresolved |

### 9.5 Grounding policy
| State | Behaviour |
|---|---|
| HIGH | Grounded answer with source reference (title + page) |
| MEDIUM | Answer + "based on limited material — check with your textbook" |
| LOW | Say material is insufficient; offer clearly labelled general explanation if educationally safe |
| NONE, grounding-critical | Do not answer as fact; say what's missing; suggest textbook/teacher |

Subject nuance: in Maths, **correctness** is established by tools, not retrieval; retrieval grounds syllabus scope, notation, method conventions and exam technique. In Sociology, named studies, sociologists, statistics and definitions **require** a retrieved citation or are omitted/labelled.

## 10. Learning Engine (state machine)

```
SELECT_TASK → PRESENT → AWAIT_ATTEMPT → EVALUATE → FEEDBACK → (NEXT | AWAIT_ATTEMPT)
                 ▲                                      │
                 └──────────── EXPLAIN (student asks) ◄─┘
```

**Help ladder**
| Level | Help | Assistance multiplier |
|---|---|---|
| L0 | None | 1.0 |
| L1 | Nudge question ("What does the question ask for?") | 0.9 |
| L2 | Targeted hint | 0.7 |
| L3 | Worked example of a *similar* problem | 0.5 |
| L4 | Reveal next step of this problem | 0.3 |
| L5 | Full solution | 0.1 |

**Escalation policy v1** (after an incorrect/partial attempt)
| Mastery | 1st miss | 2nd | 3rd | 4th |
|---|---|---|---|---|
| ≤ 2 Developing | L2 | L3 | L4 | L5 |
| 3 Competent | L1 | L2 | L3 | L5 |
| ≥ 4 Mastered | L1 | L1 | L2 | L4 |

- Explicit help request with no attempt: ask once for an attempt or first step; on second request give the next level.
- Frustration signals (≥3 help requests in 5 min, or classifier flag): escalate one level faster and offer a break.
- After L5: an isomorphic item must be attempted before objective progress is credited.
- Correct answers: every Nth (config) ask for self-explanation; Socratic Critic challenges unjustified claims once (esp. Sociology: "what evidence supports that?").
- EXPLAIN: grounded explanation (policy §9.5) ending with one check-for-understanding question.
- Pre-answer confidence (1 guessing · 2 unsure · 3 fairly sure · 4 certain) collected on practice/assessment items.
- Per turn: ≤1 retrieval, ≤3 tool calls, ≤2 LLM calls (excluding safety).

## 11. Assessment

**Selection (deterministic)**, scoring candidate objectives by: current school topic, low mastery, retention risk, open mistake patterns, upcoming assessment, time since last practice. Difficulty = mastery level ± 1, capped by config.

**Question sourcing order**
| Subject type | Order |
|---|---|
| Quantitative | past paper → textbook → parametric template (SymPy answer) → LLM-generated **only if** answer_spec is SymPy-verifiable and verification passes |
| Essay | past paper → textbook/school → LLM-generated with format check (command word, marks, AO mix) and indicative content drawn from retrieved sources |

Unverified items are never served. Assessment kinds `baseline`/`post`/`retention` use only `reserved_for_study` past-paper items and disable tutoring help.

## 12. Evaluation pipelines

### 12.1 `structured_math`
```
input: typed answer (MathLive LaTeX) or photo
photo → vision_transcriber → student confirms/edits transcription
→ parse final answer(s) (SymPy) → equivalence + accuracy rules (tools)
→ recompute intermediate values from mark scheme (tools)
→ LLM (role evaluator) awards M/A/B marks per part given tool results + mark scheme
→ consistency: tool verdict on final answer must agree with A marks; else needs_review
→ diagnose mistakes (types from config) → evaluation row → events
```

### 12.2 `essay_levels`
```
retrieve mark scheme level descriptors + indicative content + exemplars
→ command-word & length checks (tools)
→ evaluator A (model family 1) and evaluator B (model family 2) mark independently:
   AO1/AO2/AO3 marks, level band, evidence quotes from the answer, missing elements
→ agreement check vs config.max_disagreement → confidence
→ feedback composed from agreed points only
→ evaluation row (needs_review if disagreement) → events
```

**Confidence** combines transcription confirmation, tool/LLM agreement, dual-marker agreement, and retrieval state of the rubric. Below `confidence_threshold` → `needs_review`; the student still gets feedback marked "provisional", mastery is not updated until reviewed.

**Calibration**: Sociology evaluator must reach agreed thresholds against teacher-marked answers (PHASE-1 AC-E5) before its evaluations update mastery.

**Output to student** always ends with *what to do next* (from rules: mistake-fix items, similar item, or advance).

## 13. Mastery rule v1 (versioned `default_v1`)

Per student × learning objective, over evaluated attempts with `status = final`:

```
s_i  = marks_awarded / marks_available          (0..1)
a_i  = assistance multiplier of max help level   (§10)
r_i  = 0.5 ^ (age_days / 30)                     recency weight
e_i  = 1.25 if exam-style/unfamiliar item else 1.0

score = Σ(r_i · e_i · s_i · a_i) / Σ(r_i · e_i)
independent_successes = count(s_i ≥ 0.8 and help level ≤ L1)
distinct_days = number of distinct days with attempts
```

| Level | Rule |
|---|---|
| 0 Not introduced | no events |
| 1 Introduced | explanation viewed or ≤ 2 attempts |
| 2 Developing | ≥ 3 attempts and (score < 0.6 or independent_successes < 2) |
| 3 Competent | score ≥ 0.6, independent_successes ≥ 2 |
| 4 Mastered | score ≥ 0.8, independent_successes ≥ 3 across ≥ 2 distinct days, ≥ 1 exam-style success, no open high-severity mistake pattern on this objective |
| 5 Advanced | Mastered + ≥ 2 successes on stretch items (difficulty 5 / top level band) |

- `mastery_confidence = min(1, effective_evidence / 8) × mean(evaluation confidence)`
- `retention_risk`: level ≥ 3 and no success for > 21 days → `medium`; > 45 days → `high`. Recomputed nightly.
- A failed retention item on a level-≥3 objective drops one level.
- All thresholds live in config; every `mastery_state` row stores `rule_version`; projections are rebuildable from events.

`skill_profile` (AO-level) uses the same formula over criterion scores tagged to each skill.

## 14. Mistake Bank

Diagnosed mistakes from evaluations are upserted into `mistake_pattern` keyed by (student, objective, mistake_type, normalized description). `occurrences` and `last_seen` update per occurrence. Status: `open` → `improving` (2 consecutive clean attempts on that objective) → `resolved` (clean on ≥ 2 distinct days, including 1 retention item) → reopened on recurrence. Open patterns feed assessment selection and the planner.

Categories: Conceptual, Calculation, Formula, Reasoning, Misreading, Carelessness, Time management, Vocabulary, Question interpretation, Command-word (essay), Evidence (essay).

## 15. Learning Memory

At session end, LLM (role `summarizer`) proposes structured statements (`kind`, `statement`, cited `event_ids`). Deterministic validation: each statement must cite ≥ 1 event; duplicates merge; contradictions supersede older statements. Retrieval of memory into prompts is deterministic (by subject/objective, most recent active N).

## 16. Planner v1

```
capacity(day) = availability − commitments (IIT blocks, extracurriculars) − 15% buffer
candidates: school_topic practice, due revision (retention risk), open mistake fixes,
            upcoming-assessment prep, new learning, challenge
priority = 3·assessment_within_14d + 2·retention_high + 2·open_mistake_high
         + 2·current_school_topic + 1·low_mastery + 0.5·challenge
fill: protect core (school topic + due revision + mistake fixes) first,
      then practice, then challenge; cap new learning at 40% of capacity
overload: if core > capacity → drop optional, spread revision to next 3 days, tell student why
```
Rules: ≥ 1 lighter day per week; no single block > 45 min without a break; reasons shown from templates (`reason_code`). Plans are regenerated daily and on major events; inputs snapshot is stored.

## 17. Safety pipeline

```
input → rules (deterministic lexicons/patterns, incl. code-mixed English/Hinglish/Arabizi)
      → classifier (role safety_classifier, structured: category, severity, confidence)
      → policy table (category × severity → response template + action)
      → escalation → incident + audit
output → checks: no human claims, no personal-data requests, age-appropriate,
         academic-integrity (coursework), grounding labels present
```

| Category | Examples |
|---|---|
| `self_harm` | ideation, intent, method questions |
| `abuse_exploitation` | disclosure of abuse, grooming patterns |
| `sexual_content` | any sexual content |
| `violence` | threats, weapons |
| `bullying` | being bullied / bullying others |
| `personal_info` | sharing address, phone, meeting strangers |
| `dangerous_activity` | drugs, dangerous challenges |
| `hate` | hate speech |
| `academic_integrity` | "write my coursework" |
| `distress` | study stress, exam anxiety (low) |

| Severity | Action |
|---|---|
| High | Pre-written supportive response + verified crisis resources; `safety_incident`; guardian notified immediately (U4 channel) |
| Medium | Supportive templated response; incident; visible on parent dashboard |
| Low | Normal supportive handling; logged |

Failure behaviour: classifier unavailable and a rule hit → treat as the rule's severity; no rule hit → continue academic flow and log `classifier_unavailable`. Policy table and templates are versioned files reviewed by the parent. Crisis resources are config, verified by a human (U5), never generated.

## 18. Access control

- Roles: `student`, `guardian`, `admin`. Separate logins; guardian MFA required.
- Student: own data only. Guardian: data for linked students within granted scopes (Phase 1: all scopes). Admin: operations; no conversation reads without audit entry.
- Enforced twice: service-layer permission checks + Postgres RLS using `app.current_user_id` / `app.current_role` session settings.
- Every guardian read of `conversations`, `memory` or `safety` is audit-logged.
- Student UI states what linked guardians can see (from current scopes).

## 19. LLM Gateway

- Interface: `gateway.run(role, prompt_name, variables, schema, *, request_id) -> Result[T]`.
- `roles.yaml` maps role → primary model, fallback model(s), temperature, max tokens, timeout.
- Roles: `tutor`, `evaluator_a`, `evaluator_b`, `vision_transcriber`, `classifier`, `safety_classifier`, `grounding_check`, `question_writer`, `summarizer`, `tagger`.
- Budget is not a constraint: choose the strongest model per role **that wins the role's eval**; use different model families for `evaluator_a` and `evaluator_b`.
- Structured output: JSON schema request where supported; always Pydantic validate; 1 repair retry; then typed error.
- Every call writes `llm_call` (tokens, cost, latency, fallback). Prompts are versioned files; prompt version is recorded on every output that is persisted.

## 20. Error handling

| Failure | Behaviour |
|---|---|
| No retrieval / low confidence | Grounding policy §9.5 |
| Contradictory sources | Prefer higher authority tier; if same tier, state disagreement and refer to textbook/teacher; log |
| LLM timeout / provider error | Fallback model per role; then "I'm having trouble right now — your work is saved" |
| Invalid structured output | 1 repair retry → typed error → no persistence of partial results |
| Tool failure (SymPy parse) | Ask student to confirm/re-enter expression; evaluation → `needs_review` if unresolved |
| Transcription uncertain | Require student confirmation before evaluation |
| Evaluator disagreement | `needs_review`; provisional feedback; no mastery update |
| Safety classifier failure | §17 failure behaviour |
| DB failure | Fail request; no partial writes (transactions); client retries idempotently (idempotency keys on submissions) |
| Network failure (client) | Draft answers kept locally; resubmit with same idempotency key |

## 21. Observability

Trace per request (`request_id`) across router → retrieval → tools → LLM → events. Record: path, subject, intent, model, latency, tokens, cost, retrieval count/state, tool calls, evaluation confidence/status, errors, fallbacks. Dashboards (Phase 1, simple): latency p50/p90, fallback rate, `needs_review` rate, retrieval-state distribution, safety incidents, cost/day.

## 22. Testing & evals

| Layer | Scope |
|---|---|
| Unit | router resolution, help-ladder policy, mastery rule, mistake status transitions, planner fill, accuracy/sig-fig tool, SymPy equivalence, RLS/permission checks, safety rules |
| Integration | ingestion → retrieval; tutoring turn end-to-end with recorded LLM responses; evaluation pipelines; event → projection rebuild equivalence |
| AI evals (`evals/`) | Retrieval (recall@k, state accuracy); grounding/hallucination (esp. Sociology citations); evaluator agreement vs gold marks; question verification pass rate; pedagogy (does tutor withhold answer appropriately); age-appropriateness |
| Safety | Adversarial suite: direct and indirect self-harm, code-mixed language, jailbreaks via "roleplay"/"for a school project", coursework requests, personal-info sharing |
| E2E | Playwright: learn → practice → photo answer → feedback → mastery → My Day |

Evals run on every prompt/model/config/rubric change; results stored in `evals/reports/`.

## 23. Security & privacy controls

TLS everywhere; encryption at rest (DB + object storage); secrets in environment/secret manager; guardian MFA; RLS; least-privilege DB roles (`learning_event` insert-only); daily backups with a tested restore; data export and deletion per student; retention periods documented (conversations 24 months default, reviewable); OpenRouter privacy settings verified and documented; no student data in URLs or logs.

Legal position: Phase 1 is private family use. **Before any multi-student use**, obtain legal review covering UAE PDPL and India's DPDP Act 2023 (including verifiable parental consent and restrictions on tracking/behavioural monitoring of children) and exam-board terms for any past-paper content.

## 24. API surface (Phase 1)

| Area | Endpoints |
|---|---|
| Me | `GET /me` |
| Curriculum | `GET /subjects`, `GET /subjects/{id}/tree`, `GET /objectives/{id}` |
| Enrollment | `GET/PUT /students/{id}/availability`, `CRUD /commitments`, `CRUD /teaching-plan`, `CRUD /upcoming-assessments`, `POST /school-results` |
| Knowledge (admin) | `POST /sources`, `POST /sources/{id}/documents`, `POST /sources/{id}/ingest`, `GET /sources/{id}/report`, `POST /knowledge/search` (debug) |
| Tutoring | `POST /tutor/sessions`, `POST /tutor/sessions/{id}/turns` (SSE), `POST /tutor/sessions/{id}/help`, `POST /tutor/sessions/{id}/end` |
| Attempts | `POST /attempts` (text or image upload, idempotency key), `PUT /attempts/{id}/transcription` |
| Assessment | `POST /assessments`, `GET /assessments/{id}`, `POST /assessments/{id}/submit` |
| Evaluation | `GET /evaluations/{id}`, `GET /evaluations/review-queue`, `POST /evaluations/{id}/override` |
| Mastery | `GET /mastery?subject=`, `GET /mastery/{objective_id}/evidence` |
| Mistakes | `GET /mistakes`, `PATCH /mistakes/{id}` |
| Plan | `GET /plan/today`, `POST /plan/regenerate`, `PATCH /plan/items/{id}` |
| Progress | `GET /progress/summary`, `GET /guardian/students/{id}/overview` |
| Safety | `GET /safety/incidents`, `PATCH /safety/incidents/{id}` |
| Studies | `POST /studies/assignments`, `GET /studies/{subject}/results` |
| Audit | `GET /audit` (admin) |

## 25. Implementation notes (as built)

Recorded as decisions are made during implementation; these take precedence over earlier sections.

| Date | Area | Decision |
|---|---|---|
| 14 Sep 2026 | Python | 3.14 runtime (3.12+ supported); `uv` via `python -m uv` |
| 14 Sep 2026 | DB roles | Superusers bypass RLS, so the API uses the non-superuser `scholr_app` role. The owner role is for migrations only. Append-only tables also lose UPDATE/DELETE privileges |
| 14 Sep 2026 | Curriculum model | `topic` is a tree (depth 0 = content area / unit, depth 1 = textbook chapter); `learning_objective` = textbook section or coursebook key question. Syllabus-level verification pending (U11) |
| 14 Sep 2026 | Knowledge | Added `document_page` (per-page extracted text, extraction method, model, prompt version) so chunking can be re-run without re-OCR |
| 14 Sep 2026 | OCR | Both textbooks are scans without text layers. `page_ocr` role = `google/gemini-3.5-flash` (≈ $0.02/page, handwriting ignored), fallback Claude Sonnet 5 |
| 14 Sep 2026 | Embeddings | `baai/bge-m3` via OpenRouter, 1024 dimensions, HNSW cosine index |
| 14 Sep 2026 | Telemetry tables | `audit_log` / `llm_call` use client-side timestamps so INSERT never needs RETURNING (roles that write them cannot read them) |
| 14 Sep 2026 | API auth | Bearer JWT. `AUTH_MODE=dev`: HS256 tokens minted by `app.jobs.dev_token` (refused in prod). `AUTH_MODE=jwks`: external identity provider; issuer and audience required. The token proves identity only — role, student record and guardian links come from the database. Guardians need an MFA `amr` claim (`AUTH_REQUIRE_GUARDIAN_MFA`) |
| 14 Sep 2026 | App factory | `uvicorn app.main:create_app --factory`. One transaction per request with RLS context bound from the principal; tests inject a session factory on the test database. Error body is always `{"error": {"code", "message"}}`; validation errors list field locations only |
| 14 Sep 2026 | OCR cost | `gemini-3.5-flash` measured at $0.026/page (≈1.7k input / 2.6k output tokens). `google/gemini-2.5-flash-lite` — chosen in the family's AI-Investo project for low token cost — is the candidate. `app.jobs.ocr_eval` screens a model against stored pages (prose-word F1, LaTeX-token F1, cost/page) before `roles.yaml` changes |
| 14 Sep 2026 | Learning events | One Pydantic payload schema per event type with `extra="forbid"`, so ids/numbers/flags only — text cannot enter the log. `attempt_evaluated`, `evaluation_overridden`, `explanation_viewed`, `mistake_diagnosed` must name ≥ 1 objective. Future timestamps (> 5 min) and naive datetimes are rejected |
| 14 Sep 2026 | Mastery projection | Features call `events.append` then `mastery.project` in the same transaction. Evidence = `attempt_evaluated` with status `final`, or any evaluation later replaced by `evaluation_overridden` (confidence 1.0, original flags kept); `needs_review` never counts. `mastery.rebuild` recreates a student's rows from events and must equal the incremental result |
| 14 Sep 2026 | Mastery API | `GET /mastery?subject_id=&student_id=` and `GET /mastery/{objective_id}/evidence?student_id=`. `student_id` defaults to the caller's only visible student; guardians need the `mastery` scope |
| 14 Sep 2026 | OCR per source | Budget decision (user): all textbook OCR on `google/gemini-2.5-flash-lite`, no fallback to pricier models. Manifest fields choose per source: `ocr_role`, `ocr_prompt`, `ocr_output` (`json`/`markdown`), `ocr_dpi`, `ocr_bands`, `ocr_postprocess`. Sociology coursebook → `page_ocr_text` (prose content F1 0.988, $0.0005/page; last pages with `page_ocr_md`). Collins Maths → `page_ocr_math` + `page_ocr_math_md`, Markdown output, 220 DPI, `unicode_math_to_latex` (12-page screen: content F1 0.978, LaTeX-expression match 0.72 vs gemini-3.5-flash, no escape damage, $0.0006/page). Markdown output because JSON made low-cost models corrupt LaTeX backslashes (`\times` → TAB + "imes"); `ingest repair` fixes such pages deterministically. Known residual errors on dense notation (÷ read as +, some root indices): textbook text is for retrieval/grounding; textbook-derived questions still need verification before serving. First 179 Collins pages remain from gemini-3.5-flash |
| 14 Sep 2026 | Question bank | MJ24 0580 Paper 21 imported: 28 items, all verified (marks total 70/70, SymPy exact-value checks). Extractor stays on Claude Sonnet 5 (quality-critical, low volume) |
| 14 Sep 2026 | Attempts | `POST /attempts` (typed working + final answer, idempotency key), `POST /attempts/photo` (multipart, ≤ 4 PNG/JPEG/WebP ≤ 8 MB, type sniffed from bytes), `POST /attempts/{id}/transcribe` (retry), `PUT /attempts/{id}/transcription` (student confirms, AC-E3), `GET /attempts/{id}`, `GET /questions/{id}` (no answer or scheme). Only `verified` items are served; `reserved_for_study` items only inside baseline/post/retention assessments. Added `attempt.final_answer`, `attempt.transcription_meta`. Photos stored under `UPLOADS_DIR` (gitignored) as `private://uploads/...` references. Help level is derived server-side from `help_given` events in the session, never sent by the client |
| 14 Sep 2026 | Evaluation module | `evaluation` table moved to `modules/evaluation`. `POST /attempts/{id}/evaluate` (idempotent: returns the existing evaluation), `GET /evaluations/{id}`. Three steps: load (transaction) → pipeline (no transaction during the LLM call) → persist + events + projections (transaction). Pipeline chosen by `subject_configs/*.yaml` `evaluation.pipeline`; `essay_levels` returns 501 until built |
| 14 Sep 2026 | structured_math v1 | `app/tools/answer_check.py` checks the final answer deterministically (SymPy exact value + Cambridge accuracy, mark-scheme ranges, printed answers, expression equivalence — form-assessed commands such as "Factorise" are `not_checked`, coordinates, sets). Evaluator role `evaluator_a`, prompt `maths_mark/v1`. `needs_review` if: tool and model disagree on the final answer (AC-E2), award codes don't sum to marks, full marks for a wrong answer, unreadable final answer, unknown mistake category, or confidence < config threshold (0.75). Confidence = model confidence +0.05 when the tool agrees, ×0.95 for photo answers, capped at 0.5 when any issue is raised. Next step always present (AC-E7) |
| 14 Sep 2026 | Mistake bank | Only `final` evaluations that lost marks emit `mistake_diagnosed` (a full-marks answer records no mistakes, even habits like missing working). Allowed categories per subject come from config `mistake_categories` (subset of the mistake bank's list). Fingerprint = `category:label` (label from config `common_mistakes`, else `other`). Patterns are projected synchronously from events (open → improving → resolved per §14); descriptions come from the diagnosing evaluation. `GET /mistakes?subject_id=&status=&student_id=` (guardian scope `progress`) |
| 14 Sep 2026 | LLM errors in API | Any `LLMError` → 503 `llm_unavailable` / `evaluation_failed` with "your work is saved"; the attempt is already committed. The gateway is built on first use, so the API runs without an OpenRouter key |
| 14 Sep 2026 | Marking model | Budget decision (user): Maths marking uses role `maths_marker` = `google/gemini-2.5-flash-lite` (≈ $0.00025 per answer vs $0.027 on Claude Opus 5). Added review rule: the tool says the final answer is correct but fewer than all marks were awarded → `needs_review` (in screening the low-cost marker withheld an "nfww" mark). `app.jobs.marking_eval` screen (24 cases generated from verified items, no DB writes): 0 wrong results marked final, review rate 16.7%, tool agreement 0.96. This is a guard-rail screen, not the AC-E4 benchmark, which still needs teacher-marked scripts (U3) |
| 14 Sep 2026 | Gateway robustness | Per-role `retries` (same model, retryable errors only; enabled for low-cost roles and the extractor). Invalid JSON backslash escapes from LaTeX (e.g. `\sqrt`) are fixed deterministically before any paid repair call. `structured(..., temperature=)` override: past-paper extraction retries a page with invalid output once at 0.4 to break repetition loops. LaTeX corrupted by JSON decoding (`\times` → TAB + "imes") is repaired in marking feedback and extracted items (`app/llm/text_repair.py`) |
| 14 Sep 2026 | Question bank checks | Two deterministic item checks for every extractor: (1) `exact_value` must match the printed answer with mark-scheme ranges ignored (a range had let an exact value in radians pass for an answer in degrees); (2) every number in the extracted answer must appear in that question's row of the mark-scheme table (text layer; rows split at left-margin refs, indented numbers such as stacked fractions stay inside the row). A ref with no detectable row is "cannot check", not a failure (an earlier version wrongly demoted 0580/11 Q15, whose row the layout hides). `question_bank --recheck` re-runs both on stored items with no LLM calls, demotes verified items that fail, and restores only items a previous re-check demoted whose extraction was otherwise clean; study-reserved items are never changed. Result: 0580/21 Q21 demoted (exact value in radians) |
| 14 Sep 2026 | Extractor screening | Flash-Lite (`paper_extractor_lite`, ≈ $0.015 per paper vs ≈ $0.9 on Claude Sonnet 5) on Paper 21 against the Sonnet bank: marks agree on every matched item; with the new checks 1 of 23 item-level-verified items still has a wrong answer key (a stacked fraction read as its numerator), and one page falls into a repetition loop in about half of runs (the paper then fails its checks). Not adopted; decision with the user |
| 14 Sep 2026 | Retrieval (built) | Retrievable sources: course textbooks (tier B) and examiner reports (tier A). Question papers and mark schemes are never chunked — they are served only as `question_item`, so retrieval cannot leak answers or study-reserved items; "Answers to…" textbook sections are skipped. Chunker v1 (`knowledge/chunking.py`): heading-delimited blocks, worked examples and exercises kept whole as their own chunks, prose packed to ~1,800 chars (max 3,000). Tagging: printed page (from the nearest page with a printed label — the Sociology scan's offset changes from 18 to 14) → objective whose section starts at or before it (`page` in content/curriculum). Embeddings `BAAI/bge-m3` (all 1,980 chunks for $0.007); re-chunking reuses embeddings of unchanged chunks. Search: vector top-30 ∪ full-text top-30 → reciprocal rank fusion (+ bonus for objective-aligned chunks), no reranker model (cost). State rules deterministic (`knowledge/ranking.py`), similarity floors per subject in `retrieval.state_thresholds` (initial high 0.62 / medium 0.52 / low 0.42, to calibrate on the retrieval eval); tier D/E never ground; `grounding_check` LLM not used in Phase 1 yet. Every search writes `retrieval_log`. Debug endpoint `POST /knowledge/search` (short excerpts only; admin-only in prod) |
| 14 Sep 2026 | Safety pipeline (built) | `safety.check_input` on every student message before tutoring: rules → `safety_classifier` (Flash-Lite, advisory, runs on every message) → policy table → `safety_incident` + audit. Responses are fixed templates in `modules/safety/policy.yaml` (parent-reviewed, versioned); crisis resources are shown only when `verified: true` (U5) — none yet. High severity records `safety.guardian_notification_pending` until the notification channel exists (U4). Classifier failure never downgrades a rule hit; no hit + failure logs `safety.classifier_unavailable`. Output checks (claims to be human, personal-data requests, arranging contact) replace a tutor reply with a safe template. `GET/PATCH /safety/incidents` for guardians/admins (students cannot list incidents), every read audited. Rules v2: long numbers in a maths context are not phone numbers. Adversarial suite `evals/datasets/safety/cases.yaml` (64 synthetic cases) via `app.jobs.safety_eval`: high-severity recall 1.00, overall 0.95 with Flash-Lite and rules v2 (rules alone: 0.57 / 0.77; v1 with Flash-Lite: 1.00 / 0.92) |
| 14 Sep 2026 | Tutoring (built) | Sessions, conversations and messages moved to `modules/tutoring/models.py` (tables unchanged). Engine (`tutoring/engine.py`, pure): session state in `learning_session.state`; attempts and misses are read from events, not duplicated; help = policy tables (ask for an attempt first, escalation floor after misses, +1 per repeated request, +2 when frustrated = 3 requests in 5 min); after a full solution the next item must practise the same objective (AC-L3); `test` mode gives no help (AC-L5). Item selection: verified, non-reserved items; required objective → session objective → open mistakes and low mastery; items attempted in the last 14 days avoided. Guards: a reply below level 5 containing the answer's numbers (not given in the question) is replaced by a nudge template; grounding labels per §9.5 (NONE on citation-critical subjects → "not enough material" template, no LLM). API: `POST /tutor/sessions`, `GET /tutor/sessions/{id}`, `POST .../next`, `POST .../turns` (JSON reply; SSE later), `POST .../help`, `POST .../end`, `GET .../messages` (guardian reads audited). Prompts `tutor_help/v1`, `tutor_explain/v1`; fixed replies in `tutoring/templates.yaml`. Tutor role on Flash-Lite (budget); pedagogy eval still to build |
| 14 Sep 2026 | Mark-scheme parser | 0580 mark-scheme tables parsed by layout, no LLM (`assessment/mark_scheme.py`): papers 11/21/31/41 give marks totals 56/70/104/130, equal to the covers, and per-row marks equal the question papers' [n] allocations. Handles stacked fractions, symbol-font glyphs, bracketed vectors, powers, method-only sub-rows; diagram answers are flagged. Answers, marks and guidance now come from the table; the extractor (prompt `past_paper_extract/v2`) supplies question text only, and its exact value is checked by SymPy against the official answer. Flash-Lite v2 on Paper 21: 28 items, 13 verified, 0 wrong answer keys, $0.010. Sociology schemes have no table → v1. See docs/notes/mark-scheme-parser.md |
| 14 Sep 2026 | Planner v1 (built) | Engine `planner/engine.py` (pure) implements §16: capacity = availability − commitments (recurrence subset `FREQ=DAILY` / `FREQ=WEEKLY;BYDAY=…`, validated on input) − 15% buffer, ×0.6 on the week's lowest-availability day; priority formula as §16; core first, then practice, then challenge; new learning = a current school topic with no evidence yet, capped at 40%; assessment prep never capped; blocks ≤ 45 min. Overload drops optional items with a notice; dropped core returns on later days because its signals persist. Validation-study control objectives are excluded before crossover (AC-P2). Signals come from mastery, open mistake patterns, upcoming assessments (14 days) and the teaching plan (topic subtree). One plan per student-local date and generator version, `inputs_snapshot` stored. API: `GET /plan/today` (generates on first read), `POST /plan/regenerate` (finished items keep their status), `PATCH /plan/items/{id}` (student only; emits `plan_item_completed` / `plan_item_skipped`). Reasons and notices from `planner/reasons.yaml` |
| 14 Sep 2026 | Schedule data API | `GET/PUT /students/{id}/availability`, `GET/POST/DELETE /commitments`, `/teaching-plan`, `/upcoming-assessments`, `POST /school-results` (emits `school_result_recorded`). `student_id` query param defaults to the caller's only student; guardians need the `plans` scope (`progress` for results) |
| 15 Sep 2026 | Progress (built) | `modules/progress` stores nothing; it composes other services on request. `GET /progress/summary`: per enrolled subject, objectives by mastery level (objectives without evidence count as "Not introduced"), competent-or-better, high retention risk, open mistake patterns; the week (attempts evaluated, active days in the student's time zone, plan items completed/skipped); focus list (high-severity mistakes, then fading objectives); recent wins. `GET /guardian/students/{id}/overview` (guardians/admins): the same summary plus sections gated by scope — answers waiting for review (`assessments`), upcoming assessments (`plans`), open safety incidents by severity (`safety`, read audited); the scope list returned is what the student is shown |
| 15 Sep 2026 | Review queue and override (built) | `GET /evaluations/review-queue` (guardians/admins only, because it shows the mark scheme): `needs_review` evaluations oldest first, with question, working, final answer, AI marks and consistency issues. `POST /evaluations/{id}/override` sets marks (0..available, optional note), status `overridden`, `reviewed_by/at`; emits `evaluation_overridden` (mastery evidence at confidence 1.0) and audits `evaluation.overridden`. One review per evaluation (409 afterwards). Provisional mistake diagnoses are not added to the mistake bank on override |
| 15 Sep 2026 | Study assessments (built) | `POST /assessments` (study kinds by guardians/admins only; form code required; items must be verified, same subject, and `reserved_for_study` exactly when the kind is baseline/post/retention; duplicate forms refused; audited `assessment.created`), `GET /assessments`, `GET /assessments/{id}`, `POST /assessments/{id}/start`, `POST /assessments/{id}/submit`. Answers must belong to the test (fixes: any open study test previously unlocked every reserved item), one answer per question, none in a tutoring session. While a study test is in progress: no practice attempts and no tutoring help in any session (AC-L5). Study answers are marked only after submission; students see questions after starting and marks after submitting. Score: unanswered = 0; final only when every answer has a final or reviewed mark |
| 15 Sep 2026 | Validation study tooling (built) | Guardians/admins only (students never see arm labels or results mid-study). `POST /studies/assignments` creates one matched pair (app + control rows, objectives of the subject, disjoint, not already in a pair, method text such as the recorded coin flip; audited). `GET /studies/assignments`. `GET /studies/{subject_id}/results`: latest submitted baseline/post/retention forms; a topic's score uses items whose objectives lie wholly inside the arm (items spanning topics are counted and flagged); unanswered = 0, answers without a final or reviewed mark make the score provisional; g = (post − baseline)/(1 − baseline) on ratios; retention = retention/post; eligibility 20–70% baseline; engagement = sessions/week and active hours in the subject between baseline and post submission; LPH = gain difference / app hours. `studies/results.py` (pure) applies the §5 rule per subject: `pending`, `go_candidate` (still needs the interview and the cross-subject −0.05 check), `iterate`, `no_gain` (STOP only when both subjects show it). `POST /studies/{subject_id}/crossover` after the retention test sets `crossover_at` (audited), which ends the planner exclusion |
| 15 Sep 2026 | Learning memory (built) | Batch job `app.jobs.memory summarize` (not on the request path, so ending a session never waits for or fails on an LLM call). For each ended session not yet processed (`learning_session.memory_summarized_at`), the session's events become an id-free digest (event type, objective codes, marks, help level, mistake label — no conversation text, no answers). Fewer than 2 events → no LLM call. Role `summarizer` (Flash-Lite), prompt `memory_summarize/v1`, proposes ≤ 5 statements citing digest references; `memory/rules.py` (pure) drops statements without known evidence (AC-M3), merges near-duplicates of the same kind into the existing row's evidence, and supersedes an opposite-polarity statement on the same objective. LLM failure leaves the session unmarked for the next run. `GET /memory` (guardian reads audited, AC-S2). `memory.memory_for_prompt` gives deterministic retrieval (most recent active N) — not yet wired into tutor prompts, because changing those prompts requires the tutor eval first |
| 15 Sep 2026 | Web app (built, Phase 1) | `apps/web`: Next.js 15.5 (App Router, patched release), TypeScript, Tailwind 4, KaTeX. The browser calls only the web origin; `/api/*` is rewritten to the FastAPI server, so the API needs no CORS. Sign-in is a development token pasted once (AUTH_MODE=dev); the JWKS identity provider replaces it before any shared hosting. Student: Home (My Day, subject levels, focus, wins), Practice (question bank, pre-answer confidence, marking, hint ladder), Tests (start/answer/submit; no hints and marks hidden during study tests), My Progress, My Mistakes, AI Companion (grounding label and citations), What my parent sees (AC-S6). Parent: Overview, Review marks (override), Tests & study results, Schedule (availability, commitments, upcoming assessments), Learning notes, Safety alerts. Visual tokens from `design/home`; only Phase 1 subjects are shown (the IIT, India Explorer and Career sections in the mock-ups are later phases). Photo answers (upload, check the transcription, then marking) and the top-bar Ask box (Master Router) were added the same day; MathLive input is still to do |
| 15 Sep 2026 | Syllabus verification (U11) | Official syllabuses in `subjects/`: 0580 for 2028–2030 (Extended: Paper 2 non-calculator and Paper 4 calculator, each 2 h / 100 marks; content E1–E9) and 0495 for 2025–2027 (Paper 1 and Paper 2, 80 marks each; six topics, eighteen key questions matching the curriculum file). Both curriculum files are now `verified`; components updated. Papers before the 2025 syllabus are practice only for exam format |
| 15 Sep 2026 | Past papers (U12, partly) | 52 PDFs from PapaCambridge (0580 Papers 21/22/41/42 and 0495 Papers 11/12/21/22 with mark schemes, May/June 2025, Oct/Nov 2024, May/June 2023, plus June examiner reports) registered with text layers. Maths bank (Flash-Lite v2 extraction + no-AI mark-scheme parser): 598 items, 469 verified across 15 papers. Paper-level mismatches (marks totals, references missing from the mark scheme) are now advisories stored in item meta; only bad or duplicate references block a paper, and each item must still match its own mark-scheme row. Paper 4 extraction still misses questions on some papers (Nov 2024 41 found 100 of 130 marks), and 9 unverified leftovers from an earlier Nov 2024 41 run remain. Plus 55 SymPy-verified template items. Sociology bank (Flash-Lite with an 8000-token prose role, since 4000 truncated prose mark schemes): 259 items, 249 verified across 13 papers; June 2023 21 still extracts only 10 unverified items (page 3 output truncated on two attempts) and is left out. The question-bank job now passes each paper's own manifest notes (calculator rules, structure) to the extractor instead of one fixed 2024 note, and strips NUL characters that symbol fonts produce |
| 15 Sep 2026 | `essay_levels` (built) | `evaluation/essay_levels.py`: deterministic text checks (`tools/text_checks.py`: word count, command word, conclusion present; blank answers make no LLM call) → two independent markers, `essay_marker_a` = Flash-Lite and `essay_marker_b` = `openai/gpt-4.1-nano` (a different model family at the same price) → agreement check against `max_disagreement` (short answers ±1 mark, levels exact) → conservative agreed mark (lower of two within one mark, else rounded-down mean) → status. Prompt `essay_mark/v1`; the level guide is written in our own words in the Sociology config (`level_guide`). `calibrated: false` keeps every Sociology evaluation `needs_review` until AC-E5 is met with teacher-marked answers (U3), so parents review and mastery waits. Evaluation rows record both markers (`criterion_scores.markers`), the level band and the text checks |
| 15 Sep 2026 | Master Router (built) | `modules/routing`, `POST /route` (students): 1 open study test → `assessment_lock`; 2 subject given by the UI/session → no LLM (AC-A1); 3 keyword index over the enrolled subjects' objectives (`routing/rules.py`, pure) — confident when one subject clearly wins, objective only when it clearly beats the runner-up (otherwise choices are offered); intents from wording, `wellbeing` reuses the safety rule lexicon; 4 `classifier` (Flash-Lite, prompt `route_classify/v1`) with threshold 0.7; 5 ask with up to three choices. No gateway configured or LLM failure → ask |
| 15 Sep 2026 | Skill profile (built) | `mastery/skills.py` rule `skills_v1`: evidence = final `attempt_evaluated` events carrying `skill_marks` (new optional payload field; essay markers' AO split scaled to the agreed mark). Per answer, a skill scores awarded ÷ (marks available × syllabus weight from config `skill_weights`), capped at 1; profile = mean. Rebuilt with mastery from events (`mastery.project` / `rebuild`). `GET /skills`. structured_math does not split marks by AO, so Maths has no skill evidence yet |
| 15 Sep 2026 | Parametric templates (built) | `subject_configs/templates/igcse_maths_0580.yaml` (11 templates written for Scholr on Collins objectives), `assessment/templates.py`: seeded parameters → SymPy exact answer → printed answer following the checker's convention (short terminating decimals exactly, otherwise 3 s.f. keeping significant zeros) → the real answer checker must return `correct`, else the item is rejected. Saved as origin `template`, `verified_by: sympy`, `answer_spec.sympy_verified: true`; a new check constraint makes a verified template/generated item without it impossible (AC-E1). Job `app.jobs.templates`. No LLM-generated questions in Phase 1 (budget) |
| 15 Sep 2026 | Consent and audit (built) | `GET/POST /consents` (guardian consent or student assent for policy `privacy_v1`, idempotent), `POST /consents/{id}/withdraw` (only by the giver); both audited. `GET /audit` (admin only; RLS already limits audit reads to admin/system). Web: `/consent` page for both roles |
| 15 Sep 2026 | Guardian notification (built, channel pending U4) | `safety/notify.py` + `app.jobs.notify loop`: high-severity incidents not yet notified are delivered through a channel, then marked `notified` and audited (failures audited and retried). Channels: in-app (default — visible on the parent overview and safety page) and an HTTPS webhook when `NOTIFY_WEBHOOK_URL` is set. The payload carries no names or message text. Delivery is off the request path; a 30-second poll meets the one-minute target (AC-S3) once the job runs beside the API |
| 15 Sep 2026 | CI and backup rehearsal | `.github/workflows/ci.yml`: ruff format/check and unit tests (no database, no LLM, no copyrighted content), database integration tests against a `pgvector/pgvector:pg16` service set up with the `infra/db-init` scripts (the job fails if any test skips), web type check and build. Evals make LLM calls, so CI checks their datasets (`test_eval_datasets.py`) and the evals run locally after a cost estimate. `infra/scripts/backup_restore_rehearsal.sh`: `pg_dump` inside the container → restore into a scratch database → table-by-table row counts → cleanup (AC-O2); the dump never leaves the container |
| 16 Sep 2026 | No sign-in screen yet | Sign-in is not built (U6 hosting/identity undecided), so the web app opens the household directly: `POST /dev/session` returns a token for the seeded student or guardian, and a Student/Parent switch in the header changes account. The route exists only when the API runs with `AUTH_MODE=dev` (config already forbids that with `APP_ENV=prod`) and reports 404 otherwise, when the web app says sign-in is not set up. Replace both when real sign-in lands |
| 16 Sep 2026 | My Day timeline (planner) | `planner.engine.schedule_day` lays the day out: commitments (rrule + `start_time`) keep their own times, plan items fill the gaps in plan order, with a 5-minute gap either side; anything that does not fit keeps its place without a time. Study window 16:00-21:00 on weekdays and 09:00-19:00 at weekends — an assumption in the engine, to move to the household seed once the family confirms their hours. `PlanOut.timeline` carries the rows; the web app renders them for the student (with Done/Skip) and read-only for the guardian |
| 16 Sep 2026 | Guardian trends and suggestions | `GET /guardian/students/{id}/trends?weeks=8`: weekly topics secure (replayed from events through the mastery rule, `mastery.secure_counts_at`; mistake holds are not replayed), how answers were reached (without help / with hints / worked solution), study minutes per day this week, minutes by subject, and the family's planned minutes a day. `guardian_overview` also carries assessment readiness (topics secure of those an assessment covers) and deterministic "How you can help" suggestions. The weekly progress summary gained answers without help, mistakes fixed and study minutes. No LLM anywhere in this path |
| 16 Sep 2026 | Student home and parent overview (design/home) | Rebuilt to the two design artboards: student home has the day's stat tiles, the timeline, continue-learning cards, quick actions, progress and mastery panels and the companion card; parent overview has the four "how is she doing" tiles, weekly charts (topics secure, solved without help, help mix, study time), strengths and gaps, assessment readiness and the suggestions card. Charts are inline SVG with a validated three-step palette (colour-blind separation checked), a legend, hover values and a "show the numbers" table. Sidebar navigation is grouped like the design. Out of Phase 1 and deliberately not built: IIT Foundation and India Explorer paths, Career Explorer, Goals, session history and the period switcher |
| 15 Sep 2026 | Maths input (MathLive) | Subject config field `answer_input` (`expression` for Maths, default `text`) is exposed on `/me` enrollments. The answer box then offers a MathLive field for the final answer and a maths-line builder for working; answers are sent as `$LaTeX$`. `math_sympy` reads MathLive LaTeX (`\frac`, `\sqrt[n]`, `\cdot`, `\mathrm{}`/`\text{}` units, degrees, `\$`, `\%`). MathLive loads in the browser only, uses the app's KaTeX fonts, and falls back to a plain text box |
| 15 Sep 2026 | Learning memory in the tutor; citation rule | `tutor_explain/v2` and `tutor_help/v2` receive `learning_notes` (the latest active memory statements for the subject, `memory.memory_for_prompt`), to aim explanations and hints without quoting them or giving more help. Citations are chosen in code (`engine.usable_citations`): replies on LOW/NONE retrieval are already labelled as general explanations, so they show no sources, and invalid or repeated excerpt numbers are dropped. This fixed the tutor eval finding where off-syllabus questions cited unrelated excerpts; `tutor_v2` (42 cases) passes 42/42 |
| 15 Sep 2026 | Guardian monthly summary | `GET /guardian/students/{id}/monthly?month=YYYY-MM` (scope `progress`; mastery and plan parts need their scopes). Calendar month in the student's timezone, compared with the previous month: active days, study minutes, answers marked, settled marks (reviews settle `needs_review`), share answered with at most a nudge, sessions, mistakes found and resolved, topics last shown at competent or better, plan items, and the current focus list. Derived on request from events, mastery and plans; no LLM. Web: `/parent/summary` |
| 16 Sep 2026 | External subjects (Phase 3) | A subject config may set `taught_here: false`. That subject has no retrieval, pedagogy, evaluation or mistake block at all, because Scholr neither teaches nor marks it — `subjects.taught_config_for` refuses it, so tutoring, evaluation, retrieval, templates and the skill profile cannot touch one. `SubjectOut.taught_here` lets the web app tell the two apart without recognising subject codes. Seeded this way: the four AhaGuru IIT Foundation Grade 9 courses (Maths 29 lessons, Physics 25, Chemistry 9, Biology 6), each lesson a learning objective, with the consolidated multiple-choice test and the CBSE-pattern descriptive exam as components. Unverified: the provider publishes no syllabus document (U14) |
| 16 Sep 2026 | Concept map (built) | `concept`, `objective_concept` and `concept_prerequisite` are now populated, from committed `content/curriculum/concepts-*.yaml` via `app.seed.concepts`. `concepts-maths-grade9.yaml`: 40 concepts, 154 objective links, 47 prerequisite edges joining the 29 IIT Maths lessons to IGCSE 0580 objectives. `concept.note` records why a mapping is what it is where that needs saying — the factor theorem and Heron's formula are outside 0580, so the map names the IGCSE ground they stand on instead. Unit tests check the file for unique names, resolvable prerequisites, no cycles, real objective codes, and that every IIT lesson reaches an IGCSE objective within the trace's two hops (AC-X5) |
| 16 Sep 2026 | External training log and trace (built) | `external_training_log` (student-scoped, forced RLS): course, kind, date, duration, lessons covered, lessons struggled with, score, questions attempted/missed, weakness labels, notes. Writing one emits `external_training_logged` carrying counts only — no wording — and audits `external_training.recorded`. It is never mastery evidence: mastery means Scholr's own evaluated attempts with a help level and an evaluator confidence, which a coaching-centre percentage has neither of (AC-X3). `external_training/trace.py` (pure, no LLM) walks weak lesson -> concepts -> prerequisites (two hops) -> objectives of subjects Scholr teaches, scores each by how much it needs work (mastery level, open mistakes, retention risk), drops anything already secure (AC-X8), keeps at most two objectives per concept so one broad foundation cannot crowd out the idea the class taught, and breaks ties towards the idea closest to the class. API: `POST/GET /external-training`, `GET /external-training/summary` |
| 16 Sep 2026 | Reinforcement in the planner | New plan-item kind `reinforcement` (20 minutes), fed by `ObjectiveSignal.external_weakness`. It ranks below assessment prep, mistake fixes, revision and school topics and above ordinary practice, is capped at one a day, is dropped first when the day is full, and always names an IGCSE objective — the external course is complemented, never repeated (AC-X9, AC-X10). `plan_item.reason_detail` carries a sentence naming the class topic, so the student sees why it is there (AC-X12). Web: `/parent/iit` records a class or test and shows what it points at; `/student/iit` is the read-only view |
| 16 Sep 2026 | Subject stages | A subject config declares a `stage`, and that is the only switch engine code may branch on (AC-A2, AC-X2). `taught` = the full Subject Expertise Engine (0580, 0495). `planned` = Scholr knows the syllabus and can name a topic to revise, but has no question bank, retrieval corpus or marking for it, so the teaching blocks are absent rather than invented (0625, 0620). `external` = the student learns it somewhere else and Scholr only records what happened there (the four IIT Foundation courses). `subjects.taught_config_for` refuses anything but `taught`; `SubjectOut.stage` lets the web app tell them apart without recognising subject codes. A curriculum test enforces the rule that you cannot teach to a syllabus nobody has verified |
| 16 Sep 2026 | IGCSE Physics 0625 and Chemistry 0620 (planned) | Curricula seeded at `stage: planned`: Physics 6 topics / 24 subtopics, Chemistry 12 topics / 49 subtopics, with AO1–AO3 and the school's P2/P4/P6 paper list. Structure from the published syllabus topic lists; Term 1 coverage (all of Physics topic 1; Chemistry topics 2, 7, 8, 12) from the school's Year 10 Term 1 planner given by the parent. Both are `unverified` — no official syllabus PDF is held (U17) — so nothing is taught, generated or marked from them. The Chemistry course book in `subjects/IGCSE` is a scan with no text layer, so it was not used; reading it would need vision OCR and a cost estimate first |
| 16 Sep 2026 | Concept maps for the sciences | `concepts-physics-grade9.yaml` (18 concepts, 46 objective links) and `concepts-chemistry-grade9.yaml` (8 concepts, 26 links) join the 25 IIT Physics and 9 IIT Chemistry lessons to 0625 and 0620. Where the external course goes beyond the IGCSE grain — Archimedes' principle, gas pressure, the sign convention in uniformly accelerated motion — `concept.note` says what IGCSE ground the suggestion is standing on instead. A reinforcement target in a `planned` subject comes back with `practicable: false`: both portals show it as "revise this from the course book", and the planner never schedules it, because a plan item with no questions behind it is a dead end |
| 16 Sep 2026 | IGCSE Biology 0610 (planned) | Curriculum seeded at `stage: planned`: 21 topics, 59 subtopics, AO1–AO3, the P2/P4/P6 paper list; Term 1 = topics 1, 2, 3, 4 and 19 from the school planner. `concepts-biology-grade9.yaml` (11 concepts, 33 objective links) joins all 6 IIT Biology lessons to it. Unverified, and the course book the parent supplied is a 478-page scan with no text layer, so the structure came from the 0610 topic list; the manifest records its licence and says to price an OCR run before ingesting. All four IIT Foundation courses now trace |
| 16 Sep 2026 | Suggestions spread across classes | The reinforcement list is built round-robin over the classes that produced it — the best suggestion from each, then the second from each — so the newest bad class cannot fill it while three other courses stay invisible. With one class logged it is just the ranked list (a flat per-class cap was tried first and throttled the feature to two suggestions whenever only one class had been logged). The per-concept cap of two still applies inside that |
| 16 Sep 2026 | Science syllabuses verified (U17) | The official 0625, 0620 and 0610 syllabuses for 2026-2028 arrived, and all three curricula were rebuilt from them by script — `pymupdf` reads each PDF's subject-content section, so the committed file carries Cambridge's own codes and wording rather than a transcription. Physics and Chemistry were already right (three wording fixes); Biology had three real errors: 2.1 is "Cell structure" not "Cell structure and organisation", topic 12 has a 12.1 Respiration above aerobic and anaerobic, and topic 16 has a 16.5 Sex hormones in humans, so 0610 went from 59 to 61 subtopics. Assessment structure is now real: Paper 2 (45 min, 40 marks, 30%), Paper 4 (1 h 15, 80 marks, 50%), Paper 6 (1 h, 40 marks, 20%), the same across all three. Verification and stage are separate axes — the three stay `planned` because they still have no question bank, corpus or marking; the test only enforces that a `taught` subject is verified |
| 16 Sep 2026 | Assessment-objective tagging (Phase 2) | `ao_tagging` in a subject config says which AOs a question part carries; `app.jobs.ao_tag` applies it to the bank with no LLM, reports before it writes, and is idempotent. Sociology's rule comes from the 0495 syllabus's own "These questions assess ..." statements, expressed as a mark tariff so it also holds for the 2023/2024 papers set under the previous syllabus: source-based Paper 1 Q1(a)(i-iii) -> AO2+AO3, up to 6 marks -> AO1+AO2, 8 marks and above -> AO1+AO2+AO3. All 259 verified Sociology items tagged (158 / 95 / 6); 213 command words were normalised to lower case at the same time, since the extractor had kept the paper's capitalisation and "Describe" and "describe" were different words to every reader of the bank |
| 16 Sep 2026 | Exam readiness (built) | `modules/readiness` stores nothing and calls no LLM. `GET /subjects/{id}/readiness`: per assessment objective her share of marks against the syllabus weighting, per topic her share and objectives secure, command words weakest first, days to the exam, and a single weighted share renormalised over what can be judged. Two refusals are deliberate — nothing is claimed below 20 available marks, and an answer whose marks were not split by objective counts as coverage only, because spreading a whole-question mark across its AOs would invent per-objective evidence. `GET /subjects/{id}/past-papers` lists the 13 whole Sociology papers in the bank, separating what the bank holds from what a candidate actually sits (both papers offer a choice of questions) |
| 16 Sep 2026 | Timed past-paper sitting (Phase 2) | `POST /subjects/{id}/sittings` builds a real paper: the bank holds every question, but a candidate answers only some — Sociology Paper 1 is Q1 plus one of Q2/Q3, Paper 2 is two of three — so the sitting asks which she is answering and refuses a choice the paper does not offer. The rule is `paper_structure` in the subject config, from the syllabus's assessment section. A MJ25 Paper 1 sitting is 14 parts and exactly 80 marks over 120 minutes, created as an `exam_style` assessment carrying `paper_ref` and `duration_min`; starting the same paper again resumes rather than duplicating. The clock reports an overrun but never cuts her off mid-answer — losing the work would be a worse failure, and running out of time is itself readiness information |
| 16 Sep 2026 | Command-word drills | A drill is a practice session narrowed to one command word (`learning_session.command_word`), so the picker serves only questions asking for it; the readiness view ranks command words weakest first, and a drill on a word the bank cannot supply is refused rather than opened empty. Found while testing: the session picker only avoided items whose answers had been *submitted*, so pressing "next" without answering served the same question again — which made a drill useless. `SessionState.served_item_ids` now remembers the last 20 items of the session, bounded so a long session comes back round rather than running out |
| 16 Sep 2026 | Study Critic (built, Phase 2) | `modules/critic`: five pure rules over `learning_event` with no LLM — long gaps between study days, a week's minutes bunched onto one day, plans repeatedly unfinished, a rising share of answers needing help, one enrolled subject going quiet. Wording comes from `critic/patterns.yaml` templates in two voices, and `GET /study-patterns?audience=` lets the student read the guardian's wording of the same observation; both see the same list, only the phrasing differs (AC-C3). Two constraints are tested rather than trusted: a unit test greps the template file for verdict words (struggling, unmotivated, careless) and fails the build if one appears — it caught "a reminder of falling behind" in the author's own first draft — and thresholds are slack enough that silence is the normal output, with an explicit "nothing stands out" line so an empty panel does not read as broken |
| 16 Sep 2026 | Goals with derived progress (Phase 2) | The `goal` table existed but held only free text. A goal now names a `measure` Scholr can count — topics secure, days studied a week, answers solved without help, open mistakes — its `target_value`, and the `baseline_value` it stood at when set, which is what stops "6 of 8 topics" reading as progress when it started at 6. Readings come from the module that owns the evidence, so `settle_achieved` marks a goal done from the numbers and nobody can claim it. "Set with the student" is enforced: a goal a parent proposes stays `proposed` until she agrees, and the agree endpoint refuses a guardian outright. A target that asks for no change, or moves the wrong way for its measure, is refused at the point of setting with the current reading in the message. `GET/POST /goals`, `POST /goals/{id}/agree|drop` |
| 16 Sep 2026 | Cross-subject links (Phase 2) | `concepts-cross-subject.yaml`: ten concepts naming the mathematics the sciences stand on — rearranging a formula, reading a gradient, area under a graph, ratio and proportion, standard form, significant figures, vectors, percentages, averages — linking 0580 to 0625 and 0620 (52 objective links). `GET /objectives/{id}/related` returns other subjects' objectives sharing a concept, one hop only, each naming the shared idea and her level on it; IGCSE Physics 1.2 Motion comes back resting on gradients, area under a graph and vectors. They are new concept names rather than additions to the Maths map because the seeder treats each file as the whole truth for the concepts it names — reusing a name would delete that concept's links in the file that owns it, so a unit test now asserts the names are disjoint across all five files |
| 16 Sep 2026 | Source folder reorganised | The family's materials moved to `subjects/IGCSE/<subject>` and `subjects/IIT`, which broke every `file:` path in the two manifests (68 of them, all repointed). New manifests record the 0625 and 0620 course books with licence and owner, but nothing is ingested for them: a `planned` subject has no retrieval corpus. The Chemistry book is a scan with no text layer, so reading it needs vision OCR and a priced run first |
| 19 Sep 2026 | Examiner-report insights (Phase 2, AC-R6) | New table `examiner_insight` (course content like `question_item`: `tenant_id`, no `student_id`, no RLS policy). Segmentation is deterministic (`assessment/examiner_reports.py`, `er-seg-v1`): paper → question → part from the report's own layout, so attribution never comes from the model. Flash-Lite paraphrases per question by block id (`examiner_report_extract/v2`); guard keeps ≤40-word points sharing no 8-word run with the report. Rows link to `question_item.source_ref`; an item shows its own ref's points plus its ancestors' (Q1(a)(ii) ← Q1(a) ← Q1) and up to 3 whole-paper points. Served only via `GET /evaluations/{id}/examiner-insights`, i.e. after marking |
| 19 Sep 2026 | Learn: streams and topic pages (docs/STUDENT-APP.md) | New module `learn` (orchestration over curriculum, mastery, assessment, mistakes, knowledge) and table `lesson` (course content, one per objective, no `student_id`, no RLS). Streams in `subject_configs/streams/streams.yaml`; subjects join by config `path`. Lessons written by role `lesson_writer` (gemini-2.5-flash-lite, 3000 tokens) from retrieval at HIGH/MEDIUM only; guard `learn/lessons.py` v5: LaTeX escape repair then drop anything still garbled, citations, 12-word copy check (shared `tools/text_overlap.py`, also used by examiner insights), names absent from cited excerpts, SymPy agreement per `pedagogy.worked_example_check`. Reading a lesson emits `explanation_viewed` (payload `lesson_id`) and projects mastery, so a topic can reach Introduced and no further |
| 19 Sep 2026 | All LLM roles on Flash-Lite (user rule) | Every role in `app/llm/roles.yaml` — PDF extraction, batch jobs and marking — runs on google/gemini-2.5-flash-lite with no fallback; `tests/unit/test_ocr_roles.py` enforces it. Changed today: `lesson_writer` (was gemini-3.5-flash; its 29 lessons rewritten), `page_ocr` default (gemini-3.5-flash), `paper_extractor` (claude-sonnet-5), `tagger` (unused), `evaluator_a`/`_b` (claude-opus-5, gpt-5.5; named by no subject), `essay_marker_b` (gpt-4.1-nano, the Sociology second marker — now the same model as marker A, sampled at temperature 0.4 so dual marking still disagrees sometimes; weaker than two model families, and not measurable until teacher-marked answers exist, U3) |
| 19 Sep 2026 | Daily practice set and past-paper hub (docs/STUDENT-APP.md step 4) | `planner/daily.py` (`daily_set_v1`, pure): up to 6 questions from today's plan, open mistakes, retention risk and Introduced topics; excludes the last 14 days, study-reserved items and control topics; stable per day by hash. New student table `daily_practice` (forced RLS), one row per day, progress read from attempts and evaluations. `GET /practice/daily`. Past-paper hub `GET /learn/subjects/{id}/past-papers` groups servable past-paper items by the chapter of their first objective, newest series first, with her last try. New helpers: `assessment.latest_attempts`, `item_briefs`, `past_paper_items`; `tools.dates.local_day_start` (aware local midnight) |
| 19 Sep 2026 | Stage `lessons`; Physics lessons (docs/STUDENT-APP.md §10) | New subject stage between `planned` and `taught`: `ExplainedSubjectConfig` (retrieval + pedagogy, no evaluation); `SubjectConfig.explains`; `subjects.explained_config_for` (used by `knowledge.search` and lessons). Tutor sessions refuse non-taught subjects. Text-layer books: `chunking.detect_printed_labels` (edge numbers voted to one offset) run by `extraction.label_text_layer_pages`; headingless text starts a block per page. Curriculum objectives may list several course-book `pages`; `curriculum.objective_section_starts`. Physics coursebook: 1,240 chunks, 1,218 tagged; 24 lessons |
| 19 Sep 2026 | Timed sittings under exam conditions (PHASE-2 §9) | Every exam-conditions check uses `EXAM_STYLE_KINDS` (study tests + `exam_style` sittings): no help, no outside practice, marks after submission. `assessment.active_exam_assessment` (was `active_study_assessment`) counts a sitting only within `SITTING_HOLD` (12 h) of its start; study tests never lapse. Abandoned sittings are neither listed as sat nor resumed |
| 19 Sep 2026 | Answer units with Pint (docs/STUDENT-APP.md §10) | `app/tools/units.py` wraps Pint: textbook and LaTeX spellings normalised, `is_unit`, `display`. Subject config `pedagogy.answer_units` makes a worked example's `unit` field required; `lesson_guard_v6` drops an example whose unit Pint cannot parse. The value stays unitless so SymPy's check is unchanged. |
| 20 Sep 2026 | Local accounts, admin-approved (docs/STUDENT-APP.md D7) | Third auth mode `local`: Argon2id password in `user_credential`, sessions signed like dev tokens but issued only by `/auth/sign-in`. `registration_request` holds what an account asked for and what the admin decided; approval grants streams and enrolls through the enrollment service. `app_user.status` gains `pending` and `rejected`. Registration and sign-in routes 404 outside local mode |
| 20 Sep 2026 | Runs from one compose file (docs/RUNNING-AT-HOME.md) | `infra/docker-compose.home.yml` + a Dockerfile per app: db, one-shot migrate, api, web. Content is mounted, never baked in, so the API's content directory is configurable (`SCHOLR_CONTENT_DIR`); the web image bakes its `/api` proxy target as a build argument because Next resolves rewrites at build time. A web manifest makes the app installable on a phone |
| 20 Sep 2026 | Topic pacing (docs/STUDENT-APP.md AC-U13) | `learn/pacing.py`: a pure rule turning a topic page into its parts with minute estimates from its own content, `done` from stored evidence. Served on `TopicOut.steps`/`minutes`; the page reveals worked-example steps one at a time. No points or streaks — PRINCIPLES §Tone |
| 20 Sep 2026 | Lesson diagrams (docs/STUDENT-APP.md AC-U14) | `learn/diagrams.py`: six deterministic kinds; a model picks one from the objective's curated vocabulary (`pedagogy.diagrams`) and supplies numbers, which are recomputed and checked (SymPy, Pint) before drawing. Candidates are stored unapproved and served only once a person approves them (`app.jobs.illustrate --review/--approve`). Drawing lives in `apps/web/src/components/learn/diagrams/` |
| 20 Sep 2026 | Tutor for lessons-only subjects (docs/STUDENT-APP.md D4 amended, AC-U15) | `start_session` allows `mode: learn` wherever a subject config explains (taught or lessons); practice and test still require taught. `prepare_explanation` reads `explained_config_for`. The web "Explore with AI" panel is that Tutor opened on a lesson section, not a second path to a model |
