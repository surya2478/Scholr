# Phase 1 — Core Learning Slice (v2.1)

**Window:** 14 Sep 2026 → gate review by 21 Dec 2026 (end of Term 1).
**Goal:** prove the full learning loop works *and improves learning* on two deliberately different subjects before expanding.

## 1. Why this slice

| Subject | Why |
|---|---|
| **Maths 0580 Extended** (first) | Most verifiable: SymPy can check answers, so the core engine, evaluation, mastery and mistake bank can be validated with low ambiguity. Handwritten working forces the input problem to be solved early. |
| **Sociology 0495** (second) | Earliest exam (May/Jun 2027). Essay marking against AO1–AO3 levels is the opposite of Maths — if both run on the same engine via configuration, the architecture is proven. |

Both configs are drafted in Week 0 so the engine does not overfit to Maths. Physics follows the gate (see ROADMAP).

## 2. Scope

**In**
- Auth (separate student/guardian logins), RBAC with scopes, consent records, audit log
- Curriculum model + seed for 0580 Extended and 0495; Term 1 teaching plan
- Knowledge ingestion for the sources in §4; hybrid retrieval; validation; grounding policy
- Router (context-first), IGCSE orchestrator, Subject Expertise Engine, two configs
- Learning Engine state machine with help ladder, Socratic step, pre-answer confidence
- Question bank (past papers), Maths parametric templates, verified generation
- Evaluation: `structured_math` (typed + photo) and `essay_levels` (dual marking)
- Events, mastery v1, skill profile, mistake bank, learning memory
- Planner v1 + My Day; student progress view; guardian overview (basic)
- Safety pipeline v1 with incidents and guardian notification
- LLM gateway with telemetry; evals; validation study tooling

**Out** (see ROADMAP): other subjects, IIT integration, India Explorer, Career features, Supportive Companion, Study Critic, spaced repetition, gamification, multi-tenant onboarding, visual polish beyond clean and usable.

## 3. Weekly plan (indicative; re-plan at end of W2)

| Week | Dates | Deliverables |
|---|---|---|
| W0 | 14–18 Sep | Repo scaffold (web, api, infra, evals); CI; auth provider decision; OpenRouter account + privacy settings; source manifests; obtain materials (§4); draft both subject configs; seed eval dataset (30 Maths, 20 Sociology items) |
| W1 | 21–25 Sep | Schema + migrations + RLS; identity/RBAC/consent; audit; curriculum seed (0580 Extended objectives, 0495 Term 1 topics); teaching plan seed; LLM gateway + `llm_call`; safety rules skeleton |
| W2 | 28 Sep–2 Oct | Ingestion pipeline; chunking + tagging; embeddings + FTS; retrieval + validation; retrieval eval & threshold calibration; embeddings/reranker decision; past-paper → `question_item` import for Maths |
| W3 | 5–9 Oct | SymPy tools + accuracy rules; `structured_math` pipeline; photo → transcription → confirm; events module; mastery v1 + mistake projections |
| W4 | 12–16 Oct | Learning Engine state machine; router; tutor UI (KaTeX, MathLive, photo capture); practice flow; Maths templates + verified generation; **select validation topics (needs U2)** |
| W5 | 19–23 Oct | Planner v1 + My Day; progress + guardian overview; safety pipeline complete + notifications (U4, U5); deploy (U6); **Maths baseline test**; Maths intervention starts |
| W6 | 26–30 Oct | Sociology ingestion; `essay_levels` pipeline; calibration against teacher-marked answers (U3); Sociology config finalized |
| W7 | 2–6 Nov | Sociology tutoring + question bank + essay UI; learning memory; **Sociology baseline test**; Sociology intervention starts |
| W8 | 9–13 Nov | **Maths post-test**; fixes from real use; safety adversarial suite; eval suite in CI |
| W9 | 16–20 Nov | Hardening; review-queue UX; observability dashboards |
| W10 | 23–27 Nov | **Sociology post-test** |
| W11 | 30 Nov–4 Dec | **Maths retention test**; Maths crossover (control topics get the app) |
| W12 | 7–11 Dec | Analysis tooling; guardian monthly summary |
| W13 | 14–18 Dec | **Sociology retention test**; Sociology crossover |
| Gate | by 21 Dec | Gate review (§7) |

If the school winter break starts earlier, retention tests can run at home; record the context.

## 4. Knowledge sources for Phase 1 (Week 0 critical path)

| Source | Tier | Needed by |
|---|---|---|
| Cambridge 0580 syllabus (exam year 2028) | A | W1 |
| 0580 past papers (Papers 2 & 4), mark schemes, examiner reports | A | W2 |
| Collins Cambridge IGCSE Maths Student's Book, 4th ed. — chapters for Units 1–4 | B | W2 |
| School Maths PPTs/worksheets (Teams) | C | W2 |
| Cambridge 0495 syllabus (exam year 2027) | A | W1 |
| 0495 past papers, mark schemes, examiner reports | A | W6 |
| Sociology textbook (U1) | B | W6 |
| School Sociology PPTs/worksheets (Teams) | C | W6 |
| Teacher-marked Sociology answers (U3) | calibration | W6 |

Each source gets a manifest (owner, licence/basis, edition, tier) before ingestion. Past-paper items are split: **reserved for study** (never used in practice) vs practice pool.

## 5. Validation study

### Design
- **Within-student, matched topic pairs, crossover.** Per subject, choose 2 pairs of objectives taught in the same window (from the school scheme of work, U2), matched on teacher/parent-rated difficulty and baseline score.
- Within each pair, assign one to **app** and one to **control** by recorded coin flip (`study_assignment`).
- Control topics: normal school study; the planner and practice selection exclude them until crossover; the tutor explains why if asked.
- **Parallel forms** A (baseline), B (post), C (retention) from `reserved_for_study` past-paper items, balanced by marks and difficulty. No help available during study tests.
- Maths marked by pipeline + parent verification against the mark scheme. Sociology marked by pipeline **and** blind human marking (parent or tutor) for all study items.
- After the retention test, control topics cross over to app support — no topic is withheld beyond the study window.

### Measures
| Measure | Definition |
|---|---|
| Normalized gain | g = (post − baseline) / (max − baseline) per arm |
| Retention ratio | retention score / post score per arm |
| Independence | share of practice items in the final intervention week solved at L0–L1 |
| Mistake recurrence | share of diagnosed patterns that recur after first diagnosis |
| Time | minutes per item; total app hours per app topic |
| Engagement precondition | ≥ 3 sessions/week average during intervention |
| LPH | (g_app − g_control) / app hours |
| Independent check | school test results on the same topics where available |

### Test forms (decided 14 Sep 2026 from the May/June 2024 papers)

**Maths**
- A study "topic" is a set of 2–4 related Collins sections (e.g. 13.3–13.5 quadratic equations).
- Each form (A baseline, B post, C retention) has **12 marks per topic**, built from Extended past-paper question parts (Paper 2/4 style: short structured parts, 1–4 marks each). Items are balanced by marks and by method-vs-accuracy marks across forms.
- Marking follows the official mark scheme (M/A/B). The pipeline marks, and the parent checks every study script against the mark scheme.
- A topic is eligible only if its baseline is between 20% and 70% of the available marks, which leaves room to improve and shows it isn't brand new.

**Sociology**
- A study topic is one coursebook key question (e.g. 2.2 "How does society control us?").
- Each form has **12 marks per topic**: one 2-mark "What is meant by", one 4-mark "Describe two" and one 6-mark "Explain how" item, matching the paper's point-marked items.
- 8/10/15-mark levels-marked answers are practised in the app but **excluded from the go/no-go measure**, because single-script marking variance is too high for an N = 1 decision. They are tracked as a secondary measure.
- All study items are marked blind by a human (parent or tutor) using the mark scheme. The human mark is the study score, and evaluator agreement is recorded for AC-E5.

**Supply:** one exam series doesn't provide enough topic-matched items for three forms (U12). Forms may also use teacher-set questions that come with a mark scheme in the same format. Every study item is `reserved_for_study` and never appears in practice.

### Decision rule (decided 14 Sep 2026)
Computed per subject from the stored results:
- `g` = (post − baseline) / (max − baseline) per topic, averaged by arm. `retention` = retention score / post score, averaged by arm.
- **GO** requires all of:
  - engagement ≥ 3 sessions/week on average during the intervention
  - mean g(app) − mean g(control) ≥ **0.15** in at least one subject, and no subject below **−0.05**
  - retention(app) ≥ retention(control) − **0.05**
  - the student wants to keep using it (short structured interview)
- **ITERATE** — engagement below 3 sessions/week, or a gain difference between 0 and 0.15, or mixed results between subjects. Fix adoption or the weakest loop step, then rerun on the next topic pair.
- **STOP / RETHINK** — engagement met, but the gain difference is ≤ 0 in both subjects.

This is N = 1: results are directional evidence, not statistical proof. Any later change to this rule is recorded here with a date and reason, and must be made **before** the relevant baseline is taken.

## 6. Acceptance criteria

Each criterion is testable. IDs are referenced from tests and PRs.

### Architecture
- **AC-A1** Inside a session with subject/objective set, a tutoring turn makes zero router LLM calls (asserted via `llm_call`).
- **AC-A2** Engine code contains no subject-specific branches; adding a field to a config changes behaviour without engine edits (review + grep check in CI). — Automated check added 15 Sep 2026: `tests/unit/test_architecture_rules.py` (no subject names in engine string literals, no comparisons of subject fields with literals); runs in CI.
- **AC-A3** Rebuilding `mastery_state`, `mistake_pattern`, `skill_profile` from `learning_event` yields identical rows.
- **AC-A4** `learning_event` rejects UPDATE/DELETE at the DB permission level.
- **AC-A5** Phase 1 retrieval never returns chunks from a subject other than the session subject (except tier A/E general reference, labelled).

### Knowledge & grounding
- **AC-K1** Every chunk has source, tier, subject, objective/topic tags, page ref; ingestion report lists untagged chunks.
- **AC-K2** Retrieval eval: recall@8 ≥ 0.85 on the benchmark; retrieval state matches the labelled expected state ≥ 80%.
- **AC-K3** For NONE-state grounding-critical questions, the response contains no unlabelled factual answer (eval).
- **AC-K4** Sociology responses contain zero named studies/sociologists/statistics without a retrieved citation or "general knowledge" label (eval over ≥ 30 prompts). — Passed 15 Sep 2026 on the live prompts (`tutor_v2`, 32 Sociology + 10 Maths prompts, Flash-Lite, $0.009): 0 AC-K4 and 0 AC-K3 violations, 42/42 cases pass. Re-run after any tutor prompt, model or grounding change.
- **AC-K5** Student notes (tier D) never appear as grounding citations.

### Learning Engine
- **AC-L1** On a first help request without an attempt, the tutor asks for an attempt/first step and does not reveal the answer.
- **AC-L2** Help levels follow the escalation table for each mastery band (unit tests + recorded-LLM integration tests).
- **AC-L3** After an L5 solution, objective progress is not credited until an isomorphic item is attempted.
- **AC-L4** Pre-answer confidence is captured on ≥ 90% of practice/assessment attempts.
- **AC-L5** Tutoring is disabled inside baseline/post/retention assessments.

### Assessment & evaluation
- **AC-E1** No generated Maths item is served unless its answer_spec passed SymPy verification (DB constraint + test).
- **AC-E2** Maths final-answer verdicts: 100% agreement between tool and awarded A marks, otherwise `needs_review`.
- **AC-E3** Photo answers cannot be evaluated before the student confirms the transcription.
- **AC-E4** Maths evaluator: total marks within ±1 of gold on ≥ 90% of 40 benchmark scripts. — Synthetic run 15 Sep 2026 (`app.jobs.marking_eval --run`, Flash-Lite, 40 scripts from verified items: correct, correct with working, wrong): within ±1 of gold 0.90, no wrong result marked final, tool agreement 0.93, but only 62% of correct answers got full marks (the rest went to review) and the review rate was 0.30. Not yet met in full: gold marks are synthetic until teacher-marked scripts arrive (U3).
- **AC-E5** Sociology evaluator (after calibration): short answers within ±1 mark of teacher on ≥ 85%; extended answers in the same level band on ≥ 80% of calibration scripts. Until met, Sociology evaluations are `needs_review`.
- **AC-E6** Evaluations below confidence threshold never change `mastery_state`.
- **AC-E7** Every evaluation shown to the student includes at least one concrete next step.

### Mastery, mistakes, memory, planner
- **AC-M1** Mastery rule v1 unit tests cover every level boundary and retention-risk transition.
- **AC-M2** A diagnosed mistake appears in My Mistakes within the same request cycle and influences the next practice selection.
- **AC-M3** Every learning memory statement cites ≥ 1 event.
- **AC-P1** My Day never exceeds computed capacity; IIT commitment blocks are respected; overload drops optional items first and shows the reason.
- **AC-P2** Validation control topics never appear in plans or practice before crossover.

### Safety, privacy, audit
- **AC-S1** Student cannot read another student's or guardian-only data (RLS test with direct SQL + API test).
- **AC-S2** Guardian reads of conversations/memory/safety create audit entries.
- **AC-S3** High-severity test inputs produce the pre-written response, an incident, and a guardian notification within 1 minute.
- **AC-S4** Safety adversarial suite (≥ 60 cases incl. code-mixed language and coursework requests) passes at 100% for high-severity recall, ≥ 90% overall.
- **AC-S5** Application logs contain no message or answer text (log scan test). — Tests added 15 Sep 2026: static rule on every log call and no `print` in engine code (`test_architecture_rules.py`), plus a runtime scan of all log records during a tutoring turn, a hint, an answer and its marking (`test_tutoring.py::test_logs_carry_no_conversation_or_answer_text`).
- **AC-S6** Student UI shows what guardians can see.

### Observability & ops
- **AC-O1** Every LLM call has an `llm_call` row with role, model, prompt version, tokens, cost, latency.
- **AC-O2** Backup restore rehearsed once successfully before W5 go-live. — Passed 15 Sep 2026 on the dev database (`infra/scripts/backup_restore_rehearsal.sh`: dump, restore into a scratch database, all 50 tables' row counts within range); repeat on the hosted database once U6 is decided.

### Evidence
- **AC-V1** Study assignments, forms, and all three test rounds exist for both subjects with results stored.
- **AC-V2** Gate report computes all §5 measures from stored data (no manual spreadsheets as source of truth).

## 7. Gate review (by 21 Dec 2026)

Inputs: gate report (AC-V2), acceptance criteria status, eval reports, safety incident summary, cost/latency summary, student feedback (short structured interview), guardian feedback.
Output: GO / ITERATE / STOP per §5, recorded here with date and reasons.

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Materials not obtained in time (digital textbook copies, past papers) | High | W0 owner + dates; start with syllabus + past papers which unlock most of Maths |
| Student does not use it regularly | Medium–High | Involve her in W4 UI review; 10–15 min sessions; phone-first; engagement precondition in gate |
| Handwriting transcription unreliable | Medium | Mandatory confirm step; MathLive typed fallback; track correction rate |
| Sociology evaluator fails calibration | Medium | Needs-review mode still gives provisional feedback; more exemplars; rubric prompt iteration |
| Scope slip | High | Re-plan at end of W2; Sociology slice may slip to W8 without moving the Maths study |
| School teaches validation topics outside expected window | Medium | U2 scheme of work before W4; choose topics ≥ 2 weeks ahead of school coverage where possible |
| Over-reliance on AI answers | Medium | Help ladder; independence metric reviewed weekly |
| Copyright mishandling | Low | Private storage, manifests, short excerpts only, no redistribution |

## 9. Inputs needed from the user

| # | Item | Needed by |
|---|---|---|
| U2 | Term 1 week-by-week scheme of work (Maths, Sociology) | W4 (9 Oct) |
| — | Digital copies / scans: Collins Maths 4th ed. Units 1–4 chapters; school Maths PPTs/worksheets | W2 (28 Sep) |
| — | 0580 and 0495 past papers, mark schemes, examiner reports (via school or Cambridge access) | W2 / W6 |
| ~~U1~~ | ~~Sociology textbook title + copy~~ — received | done |
| U11 | Official syllabus PDFs (0580 for 2028, 0495 for 2027) | W4 (9 Oct) |
| U12 | 2–3 more past-paper series with mark schemes per subject | Maths W4 (9 Oct), Sociology W6 (26 Oct) |
| U3 | 10–20 teacher-marked Sociology answers; some marked Maths work | W6 |
| U4 | Urgent safety notification channel | W5 (19 Oct) |
| U5 | Verified UAE and India crisis resources (parent-reviewed) | W5 |
| U6 | Hosting preference/region (also unblocks real sign-in: the app currently opens the seeded household with no sign-in screen, dev mode only) | W5 |
| — | Agreement on the §5 decision rule | before W5 baseline |
