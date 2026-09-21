# Phase 3 — IIT Foundation integration

**Started:** 16 Sep 2026, on the user's instruction, ahead of Phase 2 (see §7 for what that costs).
**Goal:** make the 6 h/week of external IIT Foundation coaching *visible* inside Scholr and let it steer
IGCSE work — without repeating a minute of it.

## 1. The rule this phase is built around

> **Complement, never duplicate.** Scholr does not teach the IIT syllabus. It records what happened in the
> external class, traces each weakness down to the concept it rests on, and reinforces that concept **in the
> subject we do teach** (IGCSE Maths today).

Three consequences, enforced in code:

1. IIT subjects are marked `taught_here: false` in their subject config. No practice, tutoring, question bank
   or evaluation is offered for them, and the planner never schedules an IIT lesson.
2. External scores never enter `mastery_state`. Mastery means *our* evaluated attempts, with help level and
   evaluator confidence attached; a coaching-centre percentage has none of that. External standing is its own
   projection, derived from `external_training_log`.
3. A reinforcement item always names an **IGCSE objective**, with the external weakness as its reason.

> **Amended 19 Sep 2026 (user decision D2, `docs/STUDENT-APP.md`).** The user chose to let Scholr *teach* IIT
> Foundation subjects as well. The rule above still holds for every IIT subject at stage `external`, which is all
> of them today. An IIT subject may move to `taught` — and only then gets practice, tutoring and marking — once it
> has a verified question bank, retrieval corpus and marking like any other subject. Consequence 2 is unchanged:
> coaching-centre scores never enter `mastery_state`, whatever the stage.

## 2. The student's external programme (from `subjects/IIT`, 16 Sep 2026)

Provider: AhaGuru, Grade 9 Foundation (IIT-JEE / CBSE / NEET), attended as three 2 h classes a week
(Mon Biology, Thu Physics+Chemistry, Sat Maths — already in the household seed as `iit_class` commitments).

| Course | Lessons | In scope this phase |
|---|---|---|
| Math Foundation for Std 9 | 29 | **Yes** — traced to IGCSE Maths 0580, which Scholr teaches |
| Physics for Std 9 | 25 | **Yes** (added 16 Sep 2026) — traced to IGCSE Physics 0625, which is `planned`: suggestions name a topic to revise, not work to do here |
| Chemistry for Std 9 | 9 | **Yes** (added 16 Sep 2026) — traced to IGCSE Chemistry 0620, same caveat |
| Biology for Std 9 | 6 | **Yes** (added 16 Sep 2026) — traced to IGCSE Biology 0610, which is `planned`, same caveat |

Assessments seen in the source material:

- **Consolidated Test** — 45 multiple-choice questions, 2 h, PCMB combined.
- **Descriptive exam (CBSE pattern)** — 80 marks, 3 h, 38–39 questions in five sections (20×1 objective,
  short 2 mark, 3 mark, 5 mark, 4 mark case studies).

Physics and Chemistry became traceable on 16 Sep 2026, when the parent supplied the 0625 and 0620 course
books and the school's Term 1 planner. Both IGCSE subjects are at `stage: planned` — Scholr knows their
syllabus structure but has no questions, retrieval corpus or marking for them, so a suggestion in either
reads "revise this from your course book" and never becomes a plan item. Biology is still logged only.

## 3. Scope

**In**

- `path: IIT` + curriculum seed for the four Grade 9 courses (lesson = objective), with the two exam formats
  as components.
- Concept layer: `concept`, `objective_concept`, `concept_prerequisite` populated from a committed mapping
  file; IIT Maths lessons and IGCSE Maths objectives meet on the same concepts.
- `external_training` module: `external_training_log` (topic, date, duration, score, questions attempted,
  questions missed, weaknesses), API, `external_training_logged` event, per-topic standing.
- Deterministic trace: external weakness → concepts → prerequisite concepts → IGCSE objectives, ranked by
  how weak the foundation under them is.
- Planner: at most one reinforcement item a day, never on a class day's class hours, always an IGCSE
  objective.
- UI: log a class or test; see what it changed; parent view of external progress beside IGCSE progress.

**Out** (unchanged from ROADMAP)

- Teaching, tutoring, marking or question generation for any IIT subject.
- IIT mastery levels in the IGCSE sense, IIT retrieval corpus, JEE-style question bank.
- Physics/Chemistry IGCSE curricula (next slice), India Explorer (Phase 4), career features (Phase 5).

## 4. Acceptance criteria

### Data & architecture
- **AC-X1** Seeding the IIT curriculum is idempotent and adds no rows to any `igcse-*` subject.
- **AC-X2** No engine code branches on an IIT subject; `taught_here` is the only switch (extends the AC-A2
  check to the new config field).
- **AC-X3** `external_training_log` rows never reach `mastery_state`: rebuilding mastery from events with
  external logs present yields identical rows to a rebuild without them.
- **AC-X4** Every `external_training_log` row is student-scoped with an RLS policy, and writing one emits
  exactly one `external_training_logged` event.

### Tracing
- **AC-X5** For each of the 29 IIT Maths lessons the trace returns at least one IGCSE Maths objective, or the
  lesson is explicitly listed as "no IGCSE foundation" in the mapping file (no silent empties).
- **AC-X6** The trace is pure and deterministic: same logs + same concept graph ⇒ same ranked targets, no LLM
  call.
- **AC-X7** A prerequisite that is weaker than the concept above it is reinforced first; where nothing
  separates them, the idea the class actually taught comes first (depth alone is not evidence).
- **AC-X8** A target is never an objective already Mastered with no open mistake and no retention risk.

### Complement, not duplicate
- **AC-X9** The planner adds at most one reinforcement item per day, ≤ 20 minutes, and never schedules one
  inside a logged class's hours.
- **AC-X10** No plan item, practice item or tutoring session ever carries an IIT subject id.

### Parent & student surfaces
- **AC-X11** The parent dashboard shows external class attendance, scores and the IGCSE topics they pointed
  at — pattern, not surveillance, and no IIT question text.
- **AC-X12** The student sees why a reinforcement item is there, in one sentence naming the class topic.

## 5. Inputs needed from the user

| # | Item | Why |
|---|---|---|
| U14 | Confirm the AhaGuru lesson list is current (extracted 16 Sep 2026 from `subjects/IIT`) | The trace is only as good as the lesson list |
| ~~U17~~ | ~~Official 0625, 0620 and 0610 syllabus PDFs~~ — received 16 Sep 2026, all three verified | done |
| ~~U18~~ | ~~The IGCSE Biology 0610 course book~~ — received 16 Sep 2026 | done |
| ~~U19~~ | ~~Publisher and edition of the Biology course book~~ — Cambridge University Press, 2001 | done |
| U20 | A Biology course book matching the 2026-2028 syllabus | The copy held is a 2001 edition, 25 years older than the syllabus it is meant to support |
| U15 | How class results arrive (portal report, printed sheet, parent's word) | Decides whether logging stays manual |
| U16 | Whether Dedeepya or the parent logs the class | RBAC on `POST /external-training` |

## 6. Provenance

Lesson lists, test formats and marks extracted 16 Sep 2026 from the PDFs under `subjects/IIT`
(gitignored). Only lesson titles and exam structure are stored; no question or solution text is copied into
the repo.

## 7. What starting here costs

Phase 2 is skipped for now. Two consequences worth stating plainly:

- Only IIT **Maths** can be traced end to end. Physics, Chemistry and Biology get logging and standing, but
  their reinforcement path is empty until the Physics/Chemistry slice lands.
- Guardian dashboard v2, the Study Critic and full Sociology coverage — all Phase 2 — stay undone, so the
  parent view gains an external-training panel rather than the redesign Phase 2 planned.

## 8. Status — 16 Sep 2026

**Built and tested.**

| Acceptance criterion | Where it is checked |
|---|---|
| AC-X1 idempotent seed, no IGCSE rows touched | `tests/integration/test_external_training.py::test_seeding_the_external_curriculum_leaves_igcse_untouched` |
| AC-X2 no engine branch on an external subject | `tests/unit/test_architecture_rules.py` (now rejects `iit-` literals too), `test_subject_configs.py` |
| AC-X3 external logs never move mastery | `test_an_external_log_never_moves_mastery` (mastery rebuilt from events with logs present) |
| AC-X4 RLS + exactly one event per log | `test_rls_coverage.py`, `test_one_event_per_log_and_it_carries_no_wording` |
| AC-X5 every IIT Maths lesson reaches IGCSE | `tests/unit/test_concept_map.py::test_every_external_maths_lesson_reaches_igcse` |
| AC-X6 pure and deterministic | `tests/unit/test_external_trace.py` |
| AC-X7 weaker prerequisite first | `test_a_weaker_prerequisite_is_reinforced_before_what_stands_on_it` |
| AC-X8 secure objectives excluded | `test_secure_objectives_are_never_targets` |
| AC-X9 one reinforcement item a day, ≤ 20 min | `tests/unit/test_planner_engine.py`, `test_the_day_gets_one_reinforcement_block_at_most` |
| AC-X10 no plan item carries an IIT subject | same two tests |
| AC-X11 parent sees attendance, marks, what they pointed at | `/parent/iit` and the overview panel; `test_the_summary_points_at_igcse_work_and_says_why` |
| AC-X12 the student sees why, naming the class topic | `plan_item.reason_detail`, shown under each My Day block; same test |

**Two design decisions made while building, worth recording:**

1. *Depth is not evidence.* The first version boosted anything deeper in the prerequisite chain, which buried
   the topic the class was actually about under distant foundations whenever nothing was known about either.
   Ranking is now by how much an objective needs work; depth only breaks ties, towards the class topic.
2. *One concept may not fill the list.* A broad foundation concept (five "directed numbers" objectives) could
   crowd out everything else, so at most two objectives per concept are suggested.

**Not done in this phase.**

- All four external courses now trace. Physics, Chemistry and Biology suggestions are revision only: 0625,
  0620 and 0610 are `planned`, their structure is unverified (U17), and there is no question bank,
  retrieval corpus or marking behind them, so nothing is scheduled and nothing is marked. When the science
  slice lands, moving each stage to `taught` turns those same suggestions into practice with no change to
  the concept maps.
- No import of the provider's own reports: every class is typed in by hand (U15).
- The trace suggests IGCSE objectives; it does not yet pick a particular question or worked example for them.

## 9. Status — 16 Sep 2026, second pass

The parent supplied the IGCSE Physics 0625 and Chemistry 0620 course books plus the school's Year 10 Term 1
topic planner, and asked for them to be extracted and linked to the IIT courses. Done:

- **Three subject stages** replace the earlier `taught_here` flag: `taught`, `planned`, `external`. That is
  now the only thing engine code may branch on, and only a `taught` subject carries teaching blocks.
- **0625 and 0620 curricula** seeded at `stage: planned` — 24 and 49 subtopics, AO1–AO3, the P2/P4/P6 paper
  list, all `unverified` because no official syllabus PDF is held (U17).
- **Two more concept maps** — Physics (18 concepts) and Chemistry (8) — so all 25 IIT Physics lessons and all
  9 IIT Chemistry lessons reach an IGCSE objective within the trace's two hops.
- **Revision-only suggestions**: a target in a planned subject comes back `practicable: false`, shows as
  "revise this from the course book", and is never scheduled.

Three things found while building, all fixed:

1. A `planned` subject could have been logged as external training, which would have filed her school work as
   coaching-centre work. The guard now requires `stage: external` exactly.
2. The planner filtered the finished top-N suggestion list down to what it could set work on. Three fresh
   physics classes therefore pushed every maths target out of range and the day got no reinforcement at all.
   It now narrows the *search* instead, so it always finds the best target it can actually use.
3. Moving the source files into `subjects/IGCSE/` broke all 68 `file:` paths in the existing manifests. They
   are repointed, and a test now checks every manifest names a real subject with a matching syllabus code.

The Chemistry and Biology course books are both scans with no text layer, so their contents pages could not
be read; doing so would need vision OCR, which costs money and has not been authorised. Neither was needed —
the topic structure came from the syllabus topic lists and the school's planner — but it does mean the
Biology book's publisher and edition are unknown (U19).

Biology followed on the same day, once the parent supplied its course book: 0610 seeded at `stage: planned`
(21 topics, 59 subtopics), `concepts-biology-grade9.yaml` (11 concepts), and all 6 IIT Biology lessons now
reach an IGCSE objective. With four courses being logged, the suggestion list became saturated by whichever
class was most recent, so it is now built round-robin across the classes that produced it.

## 10. Status — 16 Sep 2026, third pass

The parent supplied the official 2026-2028 syllabuses for 0625, 0620 and 0610, and the Biology book's
publisher. All three curricula are now **verified**, rebuilt straight from the PDFs rather than transcribed:
a script reads each syllabus's subject-content section, so the committed file carries Cambridge's own codes
and wording.

What the check caught — Physics and Chemistry were right (two en-dash and one "The" difference), **Biology
had three real errors**:

| | Had | Syllabus |
|---|---|---|
| 2.1 | Cell structure and organisation | **Cell structure** |
| 12 | 12.1 Aerobic, 12.2 Anaerobic | **12.1 Respiration**, 12.2 Aerobic, 12.3 Anaerobic |
| 16 | 16.5 Sexually transmitted infections | **16.5 Sex hormones in humans**, 16.6 STIs |

Biology therefore went from 59 to 61 subtopics. The concept maps still resolve with zero missing objectives,
because they reference codes and none of the corrected codes were mapped.

Assessment structure is now real rather than a note from the school planner: Paper 2 Multiple Choice
(45 min, 40 marks, 30%), Paper 4 Theory (1 h 15, 80 marks, 50%), Paper 6 Alternative to Practical (1 h,
40 marks, 20%) — identical across all three sciences.

**Verified is not the same as taught.** All three stay at `stage: planned`. Verification was the blocker on
the *syllabus*; what is still missing is the engine — question banks, a retrieval corpus, and marking that
handles units, significant figures and equation balancing. That is the science slice in ROADMAP, not a
config change. The test now enforces the rule in one direction only: a `taught` subject must be verified.

The Biology course book is a 2001 Cambridge edition — 25 years older than the syllabus it supports. Its
manifest says to treat it as explanation only and never as the authority on what is examinable (U20).
