# Phase 2 — Complete IGCSE

**Started:** 16 Sep 2026, on the user's instruction, after Phase 3 (which was itself pulled forward).
**Goal:** get Dedeepya ready for the Sociology exam in May/June 2027, and widen the app past two subjects.

## 1. What the materials allow

The user's instruction was to proceed and *"ignore subjects for which material is not shared yet"*. That
cuts the phase roughly in half. Held today:

| Subject | Syllabus | Course book | Past papers | Verdict |
|---|---|---|---|---|
| Sociology 0495 | ✅ 2025–2027 | ✅ | 13 papers, mark schemes, 3 examiner reports | **In — the priority** |
| Maths 0580 | ✅ | ✅ | 15 papers | Already taught |
| Physics 0625 | ✅ | ✅ (text layer) | — | Syllabus only; `planned` |
| Chemistry 0620 | ✅ | ✅ (scan) | — | Syllabus only; `planned` |
| Biology 0610 | ✅ | ✅ (2001 scan) | — | Syllabus only; `planned` |
| English | ❌ | ❌ | ❌ | **Out** — no syllabus code (U7) |
| Global Perspectives | ❌ | ❌ | ❌ | **Out** — no syllabus code (U7) |
| Arabic | ❌ | ❌ | ❌ | **Out** — no syllabus code (U7) |

So Global Perspectives integrity mode, multilingual retrieval for Arabic, and the English rubric are all
deferred until those materials arrive. They stay in ROADMAP; nothing about them is invented here.

The three sciences have verified syllabuses but no question bank, corpus or marking. Turning one into a
taught subject means OCR over a scanned book (~480 pages each) plus a question bank and science-specific
marking. That is its own slice, it costs money, and it has not been authorised — so they stay `planned`.

## 2. Scope

**In**

1. **Sociology exam readiness** (the stated priority; exam is May/June 2027):
   - Assessment-objective tagging of the question bank, from the syllabus's own statements. No LLM.
   - Exam readiness by AO and by topic — where she is against the weightings Cambridge publishes.
   - Timed past-paper workflow: sit a real paper under its real time limit, marked by AO.
   - Command-word drills: practise the command word she loses marks on.
   - Essay planning: plan before writing, on the extended-response questions.
   - Examiner-report insights: what examiners say candidates get wrong, per topic.
2. **Study Critic** — rule-based patterns over `learning_event`: inconsistency, cramming, unrealistic plans,
   rising help dependency, subject imbalance. Deterministic, no LLM.
3. **Limited supportive responses** for study frustration inside tutoring.
4. **Guardian dashboard v2** — goals and monthly review on top of what Phase 1/3 already built.
5. **Cross-subject relationships** through the concept graph, which Phase 3 built and populated.

**Out** (materials, or a priced job, missing)

- English, Global Perspectives, Arabic: configs, rubrics, integrity mode, multilingual retrieval (U7).
- Making any science subject `taught`: needs OCR spend and a question bank.

## 3. The Sociology exam, from the syllabus

Read from the official 0495 syllabus for 2025–2027 (`subjects/IGCSE/sociology`), 16 Sep 2026.

| | Paper 1 | Paper 2 |
|---|---|---|
| Time | 2 h | 1 h 45 |
| Marks | 80 | 80 |
| Structure | Q1 Research methods (compulsory) + Q2 Identity **or** Q3 Stratification | two of Q1 Family, Q2 Education, Q3 Crime |
| AO1 | 35% | 43% |
| AO2 | 40% | 37% |
| AO3 | 25% | 20% |

Whole qualification: **AO1 39%, AO2 39%, AO3 22%**.

Which AOs each part assesses is stated in the syllabus, and maps onto the mark tariff:

- Paper 1 Q1(a)(i–iii) — source-based — **AO2, AO3**
- parts up to 6 marks — **AO1, AO2**
- parts of 8 marks and above — **AO1, AO2, AO3**

Checked against every 2025 paper in the bank, where the structure is known exactly: Q1 (a)(i) 2, (a)(ii) 4,
(a)(iii) 6, (b) 2, (c) 4, (d) 10, (e) 12; Q2/Q3 (a)(i) 2, (a)(ii) 2, (b) 2, (c) 6, (d) 6, (e) 8, (f) 14.
The rule is a tariff rule rather than a part-letter rule so that it also holds for the 2023 and 2024 papers,
which were set under the previous syllabus and whose part structure differs.

## 4. Acceptance criteria

### Sociology readiness
- **AC-R1** Every verified Sociology item carries at least one AO, assigned by the rule above, with no LLM
  call; the rule lives in the subject config, not in engine code.
- **AC-R2** Readiness by AO compares her marks-per-AO against the published weightings, and says plainly
  when there is too little evidence to judge rather than showing a confident zero.
- **AC-R3** A timed paper can be sat end to end: real time limit, real question order, no tutoring during
  it, marked by AO on submission.
- **AC-R4** A command-word drill serves only items with that command word, drawn from the command words
  where her marks are weakest.
- **AC-R5** Essay planning never writes the answer: it returns a plan, and the tutor refuses to draft
  assessable prose.
- **AC-R6** Examiner-report insight shown with a question is attributed to its report and year, and is never
  presented as Scholr's own advice.

### Study Critic
- **AC-C1** Every pattern is derived from `learning_event` by pure, versioned rules with no LLM.
- **AC-C2** A pattern names what was observed and over what window; it never diagnoses the student.
- **AC-C3** The student sees the same patterns the guardian sees (AC-S6 holds).

### Guardian v2 and cross-subject
- **AC-G1** Goals are set with the student, and progress against them is derived, never self-reported.
- **AC-G2** Cross-subject links come from the concept graph and name the shared concept.

## 5. Sequence

Sociology readiness first, because the exam is the nearest deadline. Within it: AO tagging, then readiness
view, then the timed paper, then drills, then planning and examiner insights (both need prompts and an eval
run, so they cost money and come last).

## 6. Inputs needed from the user

| # | Item | Why |
|---|---|---|
| U7 | Syllabus codes for English, Global Perspectives and Arabic, plus their materials | Nothing for those subjects can start without them |
| U3 | 10–20 teacher-marked Sociology answers | Still open from Phase 1: `calibrated: false` keeps every Sociology mark in the review queue until AC-E5 is met |
| U21 | More Sociology past papers, if wanted, from the link the user gave | 13 papers are in the bank; more widens the timed-paper pool |

## 7. Status — 16 Sep 2026

Sociology readiness, in the order §5 set out.

| | State |
|---|---|
| AO tagging | **Done.** All 259 verified items, from the syllabus rule in the subject config, no LLM |
| Readiness by AO and topic | **Done.** `GET /subjects/{id}/readiness` |
| Timed past-paper workflow | **Done** (screen and exam-conditions fix 19 Sep — see §9). 13 papers sittable, real choice, real time limit |
| Command-word drills | **Done.** Ten command words drillable, 5–68 items each |
| Essay planning | **Done.** `POST /tutor/essay-plan`; eval 16/16, all 8 requests for a draft refused |
| Examiner-report insights | **Done** (19 Sep). 700 points from the three June reports; every item from a reported series covered |
| Study Critic | **Done.** Five rules, no LLM, both voices |
| Guardian v2: goals | **Done.** Four derived measures; proposed goals wait for her agreement |
| Cross-subject links | **Done.** Ten concepts joining Maths to Physics and Chemistry |

Two things the work turned up, both fixed:

1. **The question picker repeated itself.** It avoided items whose answers had been *submitted*, so asking
   for the next question without answering served the same one again. Harmless in ordinary practice, fatal
   to a drill. Sessions now remember the last 20 items they served.
2. **A test that could not fail.** The first timed-sitting test used a synthetic paper whose questions
   totalled 38 and 40 rather than 40 and 40, so the "a sitting is 80 marks" assertion was checking a paper
   that was never 80 marks. The fixture now asserts its own arithmetic before the test is allowed to run.
3. **A test that would have failed on a Tuesday.** The critic groups study by calendar week; its first test
   planted days at rolling seven-day offsets, so whether three crammed weeks read as three or two depended
   on which weekday the suite ran. Anchored to real calendar weeks.
4. **The wording guard caught its own author.** The rule that no pattern may diagnose the student is a test
   that greps the template file. Its first run failed on a line this author had written moments earlier —
   "a reminder of falling behind" — which is exactly the kind of phrasing that should never reach a parent's
   dashboard.

Still the binding constraint on this whole slice: **U3**. Until teacher-marked answers calibrate the essay
marker, every Sociology mark stays in the review queue, and readiness moves only after a parent has checked
the work.

## 8. Status — 19 Sep 2026: examiner-report insights (AC-R6)

The last item in §5. What the examiners said about a question now appears under a marked answer, attributed
to its report, year, paper and question.

**How.** Which question a comment is about is decided in code, not by the model. The reports share one layout
across both subjects (`Paper 0495/11` → key messages → `Question 2 …` → `(a) (i)`), so
`assessment/examiner_reports.py` splits them into per-part segments. Part labels must move forward, which
stops prose like "which (a) is not…" from starting a new part. Flash-Lite (`examiner_report_extract/v2`)
then paraphrases each question's segments in one call, answering by block id; points for blocks it was not
given are dropped. A guard keeps only points of 40 words or fewer that share no run of 8 words with the report
(UCLES copyright: only our wording is stored), and moves a whole-paper point onto a question only if the
report names that question there.

**When it is shown.** Only through `GET /evaluations/{id}/examiner-insights`, so never before an answer is
marked. The reports name the answers that scored. A timed paper is marked only on submission, so nothing
leaks mid-sitting. The UI labels it as the examiner's comment on that year's candidates, not Scholr's advice.

**Run.** `app.jobs.examiner_insights --run`: 43 calls, $0.019, no failures. 700 points kept (294 what scored,
233 lost marks, 173 advice); the guard dropped 7 that copied the report. Two segments were pure praise and
correctly yielded nothing. Coverage of verified Sociology items:

| Series | Items | With insights |
|---|---|---|
| June 2023, 2024, 2025 | 175 | 174 (the other is praise-only: 2024 P11 Q1(a)) |
| Oct/Nov 2024 | 74 | 0 — no report held for that series |

Maths: the June 2024 report was run too (59 calls, $0.012, 307 points) so the two Maths answers already
marked in the dev database show insights. June 2023 and 2025 are not yet run (~$0.04).

Found while wiring the UI and fixed: the parent review page requested `/evaluations/needing-review`, a route
that does not exist (the API route is `/evaluations/review-queue`), so the review queue never loaded. With
`calibrated: false` holding every Sociology mark for parent review, that page is the only way her Sociology
marks move.

## 9. Correction — 19 Sep 2026: the timed sitting (AC-R3)

AC-R3 was listed as done on 16 Sep, but two parts of it were not true:

1. **No screen.** `GET /subjects/{id}/past-papers` and `POST /subjects/{id}/sittings` existed only in the API; the
   web app never called them, so she could not sit a paper. Now *Timed past papers* lists every paper by subject,
   newest series first, with its real time limit and marks, offers the syllabus's own choice (Paper 1: Q1 plus Q2
   or Q3; Paper 2: two of Q1–Q3), and opens the sitting in the test page with a clock. The clock counts down from
   the server's time and never cuts her off; running over is shown and recorded.
2. **Not under exam conditions.** Help and outside practice were locked, and marks held back, only for the study
   tests (`STUDY_KINDS`). A timed sitting (`exam_style`) got none of it: the Tutor would help mid-paper and each
   answer could be marked before submission. Every such check now uses `EXAM_STYLE_KINDS` (study tests plus
   sittings): no hints or Tutor, no practice elsewhere, marks only after submission.
   `test_a_sitting_is_sat_under_exam_conditions` covers it; no test had before, which is how it passed.

**A sitting now lapses after 12 hours** (`assessment.SITTING_HOLD`). Applying exam conditions to sittings
surfaced an unsubmitted sitting in the dev record, 0495/11/MJ25, started on 16 Sep at 09:29 with no answers — most
likely left from building this feature. Under the corrected rule it would have blocked all her practice and the
Tutor until submitted. A timed paper is sat in one go, so a sitting stops holding everything else 12 hours after it
starts; it stays open for her to submit. Study tests never lapse. `test_an_abandoned_sitting_stops_locking_...`
covers it. The 16 Sep sitting itself has not been changed.
