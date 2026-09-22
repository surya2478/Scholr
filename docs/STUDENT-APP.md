# Student app — streams, subjects and topic pages

**Approved:** 19 Sep 2026, by the user, after a review of the student experience against Allen Overseas, AhaGuru
and PhysicsWallah. It runs beside Phase 1–3 and is scoped here.

## 1. Why

The engine behind Scholr is further along than what the student can see. Marking, mastery, retrieval over her
own textbooks, examiner insights and the IIT trace all exist, but she reaches them through one flat menu and a
chat box. She cannot open a subject, see its chapters, read a topic, try it, and clear a doubt on the spot —
which is the one thing every coaching portal gets right. The goal is that once she signs in she can do all of her
study and practice without leaving the app.

## 2. Decisions (19 Sep 2026)

| # | Decision | Consequence |
|---|---|---|
| D1 | **Three streams:** IGCSE, IIT Foundation, India Foundation | Streams are declared in `subject_configs/streams/streams.yaml`; a subject joins a stream through its config's `path`. No stream is recognised in code. |
| D2 | **IIT Foundation: Option B** — Scholr may later *teach* IIT subjects, not only record them | Reverses the Phase 3 rule "never teaches the IIT syllabus" (PHASE-3 §1, amended). Each IIT subject moves from `external` to `taught` only when it has a verified question bank, retrieval corpus and marking, like any subject. Until then its pages are navigable but not taught. |
| D3 | **India Foundation later** | The stream is shown as *later*. It is ROADMAP Phase 4 and needs a political-neutrality policy and a vetted source list first. |
| D4 | **Physics 0625 in, as lessons only** (stage decided 19 Sep 2026; **amended 20 Sep 2026**) | New stage `lessons`: a retrieval corpus and grounded topic lessons, no questions and no marking. **Amendment:** the Tutor now answers doubts in a `lessons` subject too — it reads the same corpus and obeys the same citation, copying and safety rules, so the line that matters is setting and marking, not explaining. Practice and test sessions still need a `taught` subject. Physics becomes `taught` with the Physics slice (question bank, units tool). |
| D6 | **Home machine first, VPS in 2–3 months** (20 Sep 2026) | No cloud yet: the app runs on the home PC under Docker and is reached on the home network / installed on her phone as a PWA. Everything built for it stays provider-neutral (one compose file, environment variables, a restore-tested backup), so the same images move to a VPS later. |
| D7 | **Accounts: register with an email, admin grants access** (20 Sep 2026) | New `AUTH_MODE=local`: anyone may register with an email address and password, but a new account is `pending` and can do nothing until the admin approves it and chooses the streams it may see. Google and mobile-OTP sign-in come later and replace only the sign-in step, not the approval. |
| D8 | **Safety notifications and helplines deferred** (20 Sep 2026) | U4 and U5 are out of step 7 at the user's request. Safety alerts stay queued and visible on the parent dashboard (`LogChannel`), which is what happens today. Go-live on a public address must not happen until they are answered. |
| D5 | **One assistant, called Tutor** | "AI Companion" is renamed. It clears doubts where she is stuck (topic, question, example); the planner says what is next; the limited supportive response handles frustration. No separate tutor / mentor / friend agents (PRINCIPLES §2). |

## 3. Scope, in order

1. **Streams and navigation.** Learn → stream → subject → chapter → topic, with her mastery on every topic and
   each subject's stage visible (*Taught*, *Planned*, *External*, *Later*).
2. **Topic page** (Maths, then Sociology):
   - **Lesson** — Scholr's own explanation drawn from her textbook with page references, key terms, worked
     examples and common pitfalls. Written once per topic, checked, stored and shared.
   - **Check yourself** — short verified bank items, marked on the spot.
   - **Exam questions** — past-paper items on the topic; examiner comments appear after marking (AC-R6).
   - **My mistakes here**, **Connections** (IIT and other subjects), and **Ask a doubt** everywhere.
3. Tutor rename and "Ask a doubt" on every question and example.
4. Daily practice set and a chapter-wise past-paper hub.
5. IIT Foundation area navigable per chapter (class log, IGCSE ground underneath, warm-up before class); IIT
   Maths taught once its bank exists (D2).
6. Physics topic pages (D4), then Chemistry and Biology after their books are OCR'd.
7. **Accounts and the app on her phone** — registration with admin approval and stream access (D7), then the
   app running on the home machine and installed on her phone (D6). Safety notifications and helplines are
   deferred (D8).

## 4. Acceptance criteria (steps 1–2)

- **AC-U1** Streams, subjects and their order come from config; engine and UI code name no stream or subject.
- **AC-U2** Every objective of a subject is reachable in at most three taps from Learn, and shows her mastery
  level when there is evidence (none otherwise — never a confident zero).
- **AC-U3** A lesson is shown only for a `taught` subject, and only if retrieval over her own course material
  reached at least the subject's grounding floor; otherwise the page says there is not enough material. No silent
  fallback to ungrounded knowledge (CLAUDE.md).
- **AC-U4** Every lesson section cites at least one excerpt, shown as book and page. A section that cites none,
  copies a run of 12 or more words from its sources, or names a study or sociologist its sources do not contain
  is removed before storing.
- **AC-U5** A worked example in a subject whose config asks for SymPy checking is stored only if SymPy computes
  the same answer the example prints. Any disagreement drops the example.
- **AC-U6** Lessons are stored with prompt version, model, source chunk ids and the checks they passed; a changed
  prompt or corpus regenerates them. Generation is audit-logged.
- **AC-U7** Reading a lesson emits `explanation_viewed` (with the lesson id). Under mastery rules v1 that can move
  a topic from *Not introduced* to *Introduced* and never higher: only evaluated attempts raise mastery.
- **AC-U8** "Check yourself" and "Exam questions" serve only verified, non-reserved items (study items stay
  unseen, PHASE-1 §5).
- **AC-U9** A validation-study control topic shows no lesson and no practice before its crossover, and says only
  that it is being learnt at school for now (AC-P2; she is not shown arm labels).
- **AC-U10** A new account can do nothing until an admin approves it: registering creates it as `pending`, with
  no student record, no enrollments and no token. Approval sets its role and grants streams; a rejected account
  can never sign in, and neither decision can be taken twice (D7).
- **AC-U11** Sign-in never says whether an address has an account: a wrong address and a wrong password are
  answered identically, registering a known address looks exactly like registering a new one, and consecutive
  wrong passwords lock the account for a fixed time. Passwords are stored only as Argon2id hashes.
- **AC-U13** A topic page says what it is made of and roughly how long it takes, is navigable from a sticky bar
  that reaches every part of it (a taught topic always shows all four, empty or not), and reveals a worked
  example one step at a time. A question is named by where it came from, never by its internal key. Every number is computed from the page's own content (reading speed, a slower rate for
  worked examples, about a minute a mark); a part counts as done only from her record — a lesson she has read,
  a question she has answered — so it still says so tomorrow. No points, levels, streaks or rewards
  (PRINCIPLES §Tone: minimal gamification; streaks are explicitly not a success metric).
- **AC-U16** A taught topic has an exam level. How the topic is examined is counted from the bank (no model).
  Where code can check the answer (Maths), one real past-paper question is solved step by step from its official
  mark scheme: the final answer must pass the check that marks hers, every mark named (M1, A1, B1) must be one the
  scheme awards, numeric working is recomputed, and for "by drawing a suitable line" questions the line is
  computed by SymPy and every line the steps name must solve the equation. A walkthrough is shown only after a
  person approves it, and the question it solves is no longer offered as one to try. Sociology gets the count
  only: Scholr does not write her exam answers (AC-R5).
- **AC-U15** "Explore with AI" on a lesson section opens the Tutor where she is reading, not a second path to a
  model: the same grounded retrieval over her own books, the same citations and grounding label, the same safety
  rules. It appears wherever the Tutor is available, which from 20 Sep 2026 includes lessons-only subjects.
- **AC-U14** A lesson may carry a diagram, and a model never draws one: it chooses a kind from the subject's
  curated vocabulary and supplies numbers, which `learn/diagrams.py` recomputes and checks (SymPy, Pint) before
  anything is drawn. A diagram is stored as a candidate and shown only after a person approves it — checks can
  prove a picture's numbers, never that it teaches the right thing.
- **AC-U12** The whole app runs on one machine from one compose file — database, migrations, API and web — with
  her material mounted, not baked into an image, and is installable on her phone from the home network (D6).

## 5. Cost

One lesson per objective, generated when first opened or by the batch job, which prints an estimate before any
run. Lessons are a batch job, so they run on gemini-2.5-flash-lite only (user rule, 19 Sep 2026): about $0.0015
per lesson, so the remaining Maths topics cost well under $1 (§7). The lesson eval runs on a sample first.

## 6. Open

- ~~**Physics stage (D4).**~~ Decided 19 Sep 2026: a new `lessons` stage (§10).
- **IIT subjects (D2).** Which course first; the `subjects/IIT` *Consolidated Test* and *Descriptive Exam*
  material is the likely question source.

## 7. Status — 19 Sep 2026: steps 1 and 2 built

**Step 1, navigation.** `GET /learn/streams`, `/learn/subjects/{id}`; web pages *Subjects & topics* →
subject (areas as headings, chapters as folds, her mastery on every topic) → topic. Streams live in
`subject_configs/streams/streams.yaml`; a unit test fails if a subject names an undeclared stream (AC-U1).
Home now shows the real streams. Three pieces of **invented data** on it were removed: hard-coded subject
cards ("12/14 Topics Ready", fixed "next topics"), an island roadmap marking topics *Mastered* that she has
never practised, and a "94% Power Level" badge in the header.

**Step 2, topic page.** `GET /learn/objectives/{id}`, `POST …/lesson` (write once, then stored),
`POST …/read`. Lesson, Check yourself, Exam questions (examiner insights after marking), My mistakes here,
Connections, and "Ask a doubt" on the page, on every question and on every worked example — the Tutor opens
scoped to the topic. "AI Companion" is now **Tutor** throughout (D5).

**Lesson checks** (`learn/lessons.py`, guard v5): LaTeX repaired first (v3: JSON decoding turns "\times" into
TAB + "imes"), then any part still holding a control character is dropped (v5: "\br" arrives as BACKSPACE + "r"
and cannot be traced back), cited excerpts only, no 12-word copies, no name its cited excerpts lack (any
capitalised word inside a sentence, accent-folded, plurals allowed — v2), SymPy agreement for worked examples
where the config asks (`pedagogy.worked_example_check`), comparing list answers value by value (v4: "the factors
of 36" were being rejected though correct). Lessons need HIGH or MEDIUM retrieval; below that the page says so
and no model is called.

**Model: Flash-Lite only.** The user's standing rule (19 Sep 2026) is that every LLM role — PDF extraction, batch
jobs and marking — runs on gemini-2.5-flash-lite with no fallback; `tests/unit/test_ocr_roles.py` fails if any
role names another model. The first 29 lessons had been written on gemini-3.5-flash, chosen by the assistant
without asking; at the user's instruction all 29 were rewritten on Flash-Lite (`--stale-only`, which replaces a
lesson in place and keeps the old one if a rewrite fails or comes back empty). The history below keeps the
3.5-flash run because it is the comparison.

**Eval run, first model** (`app.jobs.lessons`, gemini-3.5-flash; since replaced):

| | Lessons | Ready | Sections stored | Worked examples stored | Guard removed | Spend (llm_call) |
|---|---|---|---|---|---|---|
| Sociology (all 18) | 18 | 18 | 55 | 16 | 1 copied section; v2 recheck removed 4 parts from 2 lessons | $1.07 |
| Maths (first 11) | 11 | 11 | 29 | 19 | nothing; 0 worked examples failed SymPy | $0.92 |

All 16 Maths worked examples in the first ten topics were also checked by hand: every answer correct.

**Cost was about double the first estimate, and why.** With the first 4,000-token cap, most replies were cut
off mid-JSON (3,984 tokens) and the gateway's schema repair made a second call; three lessons failed outright.
The model result reports only its final call, so the job first under-reported spend. Fixed: the cap is 8,000
(the one lesson written since took a single call), and the job now reads spend from `llm_call`, retries
included.

**Eval run, Flash-Lite** (10 Maths topics, 2.5–3.3): 9 ready, 1 failed (a repetition loop to the 8,000-token cap,
twice — cap now 3,000 so a loop fails fast), 30 sections, 12 worked examples kept, **6 worked examples dropped
because SymPy did not reproduce their answer**, $0.015 in all. The 12 kept were checked by hand: all correct.
Flash-Lite's examples are simpler (3.2 sets a primary-level sweets sum), and 3 lessons needed the v3 LaTeX
repair, applied to the stored lessons with `--recheck` (no calls).

**Rewrite of all 38 on Flash-Lite, guard v5** (stored state, 19 Sep 2026):

| | Lessons ready | Sections | Worked examples | Lessons with no example | Spend |
|---|---|---|---|---|---|
| Sociology | 18 / 18 | 57 | 17 | 1 | $0.014 |
| Maths | 20 / 20 | 65 | 32 | 3 | $0.026 (two passes) |

On Maths, SymPy dropped 7 wrong worked examples in the final pass (e.g. "$16,240" for 15 000 × 1.04² =
16 224) and the v5 recheck removed 2 garbled ones. Every one of the 32 kept was checked by hand: all correct.
Against 3.5-flash, Flash-Lite writes simpler examples, gets more of them wrong before the guard (7 of 41 against
0 of 19) and leaves 3 of 20 Maths lessons with no worked example, against none — the price of the rule, paid in
fewer examples rather than wrong ones.

**All Maths lessons written (19 Sep 2026, at the user's request).** The first bulk run (prompt v1) kept only 129
worked examples and dropped 159, leaving 94 lessons with none. Diagnosis on sample drafts showed most drops were
the check, not the maths: answers wrapped in words ("The perimeter is $4w + 10$ cm", "15 tiles", "LCM = 360"),
sets written two ways ("{1, 3, 5}" against `set([1, 3, 5])`), or several values ("12 m and 42 m"). Two fixes:

- the check reads past labels, units and lead-ins, and treats "and" and set braces as lists — only words are
  removed, so the value must still match SymPy (tests pin that "16 tiles" or a missing value still fail);
- prompt `lesson_write/v2` asks for bare values in the same count and order as `answer_expression`, rules out
  "compare" or "true or false" questions as worked examples, and now holds the wording for each check mode itself
  (v1 took it from a string in `learn/service.py`, which breaks the no-inline-prompts rule).

A 15-lesson sample on v2 kept 35 examples and dropped 8; the full rewrite then kept 317 and dropped 88 as wrong.

| Maths, final | |
|---|---|
| Lessons ready | 187 of 194 (7 `not_enough_material`: her books do not cover 7.4 Rates, 16.5 Exponential graphs, 26.3 Calculating angles, 28.5 Symmetry in circles, 30.2 Reflections 1, 30.5 Rotations 2, 31.2 Pictograms well enough) |
| Sections | 584 |
| Worked examples (all SymPy-checked) | 362 |
| Ready lessons with no worked example | 36 |
| Model / prompt / guard | gemini-2.5-flash-lite / lesson_write v2 / lesson_guard_v5, one each |

Every Flash-Lite lesson call today (447, Maths and Sociology, all passes) cost **$0.44** in total.

A random sample of 25 stored examples was checked by hand: the 21 checkable without their data tables were all
correct. One problem statement was wrong in a way SymPy cannot see — "Write the recurring decimal $0.1$ as a
fraction" with answer 2/15: the recurring-dot notation for 0.1333… was lost in the model's JSON, so the answer
matched its own expression but not the question as she would read it. That lesson was rewritten; its two
examples now read 0.555… → 5/9 and 0.1212… → 4/33. SymPy checks the arithmetic of an example, not whether the
question is stated completely.

Sociology's 18 lessons stay on prompt v1: for a subject with `worked_example_check: none` the v1 and v2 wording
is the same.

**Markers.** The same rule moved every marking role to Flash-Lite. `maths_marker` and `essay_marker_a` already
were; `essay_marker_b` (Sociology's second marker) was openai/gpt-4.1-nano, chosen as a different model family so
the two markers would not share blind spots. Two markers on one model at temperature 0 would mostly repeat each
other and the disagreement check would rarely fire, so marker B now samples at 0.4: an independent reading of the
same model, weaker than a second model. `evaluator_a`/`_b` (claude-opus-5, gpt-5.5) are named by no subject and
moved too. There is no Sociology marking eval to re-run (it needs teacher-marked answers, U3); every Sociology
mark still goes to parent review because `calibrated: false`.

## 8. Status — 19 Sep 2026: steps 3 and 4 built

**Step 3, the Tutor everywhere.** One link builder (`web/src/lib/tutor.ts`) opens the Tutor scoped to the subject
and, when known, the objective. It now appears: on every topic page, question and worked example (step 2); under
every marked answer ("Ask the Tutor about this answer" — not inside a test, where tutoring is off, AC-L5); on
every mistake, with a link to its topic; and the Tutor page names the topic it was opened for, with a way back.

**Step 4a, today's practice set.** `GET /practice/daily`; table `daily_practice` (student data, forced RLS),
one row a day. The rule (`planner/daily.py`, `daily_set_v1`, pure) takes up to 6 questions: objectives on today's
plan in plan order, then open mistakes worst first, then retention risk, then topics she has only studied
(Introduced); one question each, then a second for the earliest. It never sets a question answered in the last 14
days, a study-reserved question, or a school-led study topic, prefers questions of 4 marks or fewer, and breaks
ties on a hash of the day so the set is stable for the day. Each question shows its reason from the planner's
templates (`reasons.yaml` v2). Progress is read from her attempts and their marks, never stored. Home shows the
set; the nav has *Today's practice*.

**Step 4b, past-paper hub.** `GET /learn/subjects/{id}/past-papers`: every servable past-paper question in a
taught subject under the chapter of its first tagged topic, newest series first, with her last try (marked,
waiting for a parent's check, or answered), and a series filter. Maths: 469 questions across four series.
Study-reserved questions and school-led topics are left out; untagged questions are listed last. Linked from each
subject page.

Tests: `test_daily_practice.py` (the rule), `test_daily_and_past_papers.py` (API, RLS, stability, progress);
681 pass.

**Found while building.**
- *The timed-paper workflow has no screen.* Phase 2's `GET /subjects/{id}/past-papers` and `POST …/sittings`
  (AC-R3) exist only in the API; the web app never calls them, so she cannot sit a paper. Not fixed here.
- *Verification left marks in her record.* During step 2's browser checks the assistant kept topic pages 1.3
  (Factors) and 6.1 (Crime, deviance and social control) open past the 20-second read timer, which recorded
  `explanation_viewed` events as her. `learning_event` is append-only, so they stay; under mastery rules v1
  they can only make a topic *Introduced*, and both now appear in her daily set as "you've studied this". Future
  checks use the API or close pages before the timer.

## 9. Status — 19 Sep 2026: timed-paper screen and step 5

**Timed past papers** (added before step 5 at the user's request): the screen for Phase 2's sittings, and the fix
that puts a sitting under exam conditions — see PHASE-2 §9.

**Step 5, the IIT Foundation area by lesson.** Every IIT course opens chapter by chapter like any subject (the IIT
page links to each). A lesson shows how many classes covered it and whether one was flagged hard — never a Scholr
mastery level (AC-X3). The lesson page never teaches the lesson (PHASE-3 §1). It shows:

- **Your classes on this lesson** — each logged session, marks, and "found it hard"; a form logs a new one
  (`POST /external-training`, prefilled with the lesson).
- **The IGCSE ground underneath** — `external_training.ground_under`, the Phase 3 trace started from this one
  lesson rather than from logged weaknesses, so it works before any class is logged; secure objectives are left
  out (AC-X8), syllabus-only ones say to revise from the course book.
- **Warm-up before class** — up to 3 short IGCSE questions from that ground, each question once even when it is
  tagged to two objectives underneath (found in the browser check: Q19(a) appeared twice).

On her record, Heron's formula (L17) shows two logged classes (6/20 flagged hard, 21/45 on a consolidated test),
six IGCSE objectives underneath (5.1, 27.2, 1.1, 5.2, 4.1, 4.2) and three warm-up questions.

IIT subjects stay `external` (D2): teaching IIT Maths itself waits for a verified IIT question bank.

## 10. Status — 19 Sep 2026: step 6, Physics as lessons only

**The `lessons` stage.** Between `planned` and `taught`: the subject config carries `retrieval` and `pedagogy`
(`ExplainedSubjectConfig`) and nothing to mark with. `SubjectConfig.explains` is true for `taught` and `lessons`;
lessons, retrieval and the lesson job ask for that, while tutoring, practice, marking and the daily set still ask
for `taught`. Starting a Tutor session on a subject that is not taught is now refused (`subject_not_taught`) —
before, it opened and failed on the first message. On the topic page a lessons-only subject shows its lesson and
a note to practise from the book's end-of-chapter questions; no questions, no Tutor links.

**The Physics corpus.** The coursebook (527 pages) was ingested from its text layer, no OCR. Two things had to be
built for a text-layer book:

1. *Printed page numbers.* The text layer does not mark them, so no page could be matched to the book's
   contents. `chunking.detect_printed_labels` reads numbers at each page's edge and keeps those that agree with the
   book's dominant offset (figure numbers and years at the edge disagree and are dropped): 346 of 527 pages
   labelled, all at offset 13; the rest take their neighbours'.
2. *Pages that keep their page.* The chunker starts passages at Markdown headings, which OCR'd books have and a
   text layer does not, so the whole book became one block and every passage was dated page 1. Headingless text
   now starts a new block on each page. Maths (1,012) and Sociology (693) passages were re-derived with the change
   and are identical, so their tagging, embeddings and lessons are untouched.

The book does not follow syllabus order, so an objective can now list every place it is covered
(`pages: [44, 49, 52, 68, 86]` for 1.5 Forces), read from the contents; `curriculum.objective_section_starts`
returns them all. Result: 1,240 passages, 1,218 tagged across all 24 objectives, embedded with bge-m3.

**Lessons.** All 24 written on Flash-Lite for $0.019: 76 sections, 43 SymPy-checked worked examples; SymPy
dropped 7 wrong ones and 8 with no checkable answer. A sample of 18 was checked by hand: every answer correct.
One thing to improve (units, the other, is done below): a few examples sit under a neighbouring objective (a resultant-force example under
1.2 Motion; a Hubble-constant example in km/s/Mpc where the syllabus uses per-second).

**Units (19 Sep 2026).** A Physics answer now carries its unit in its own field, so SymPy checks the number
and Pint (`app/tools/units.py`, the stack's units tool) checks the unit. Subject config
`pedagogy.answer_units: true` switches it on; prompt `lesson_write/v3` asks for the unit, and guard
`lesson_guard_v6` drops an example whose unit Pint does not recognise or that leaves it blank (an answer with no
unit must say "none"). Units are stored as the textbook prints them (`m/s²`, `Ω`, `kg/m³`), and a unit the
answer already names ("40 N to the right") is not printed twice. Rewrite of all 24 lessons: $0.020, 39 examples
kept, 2 dropped for their unit; all 39 answers and units checked by hand, all correct.

Chemistry and Biology need OCR of their scanned books before they can follow.

## 11. Status — 20 Sep 2026: step 7, accounts and the app on her phone

**Accounts (D7, AC-U10/U11).** A third auth mode, `AUTH_MODE=local`: email and password against an Argon2id
hash in `user_credential`, signed sessions issued only by the sign-in route. Registering creates a `pending`
account and a `registration_request` (migration `a1c7e5d20b43`); it has no student record, no enrollments and no
token until an admin approves it, chooses its role and grants streams — approval then enrolls a student in every
subject of each granted stream, through the enrollment service. Rejection is final. A wrong address and a wrong
password are answered identically, registering a known address looks exactly like a new registration, and eight
wrong passwords lock the account for fifteen minutes. Every step is audit-logged (`auth.registered`,
`auth.signed_in`, `auth.locked_out`, `auth.registration_approved`, `auth.registration_rejected`).

Pages: `/register`, `/sign-in`, and `/admin/registrations` where the admin decides. The entry page opens the
seeded household account in development mode as before, and redirects to sign-in when the API runs in local
mode. The first admin is made from the terminal (`app.jobs.accounts create-admin`), which also lists, approves
and rejects; it asks for the password at the prompt and never prints it.

**On the home machine (D6, AC-U12).** `infra/docker-compose.home.yml` runs Postgres, a one-shot migration step,
the API and the web app; `apps/api/Dockerfile` and `apps/web/Dockerfile` build the two images, and
`content/` is mounted so nothing copyrighted is ever baked in. The API's content directory is now configurable
(`SCHOLR_CONTENT_DIR`), which is what let the same code run from `/app` in a container. The web image bakes its
`/api` proxy target as a build argument, because Next resolves rewrites at build time. Proven end to end on 20
Sep: images built, database created, migrations applied, `/health` ok, `/auth/streams` served through the web
container's proxy, then torn down with its volume.

**Her phone.** A web manifest and app icons make Scholr installable from the home network: it opens full screen
with its own icon. It is reachable at home only — going public needs the deferred safety work (D8) and HTTPS.
`docs/RUNNING-AT-HOME.md` is the runbook: setup, moving the existing database over, the first admin, the phone,
backups and upgrades, and what changes on a VPS.

Not yet: safety notifications and verified helplines (D8, CONTEXT U4/U5), which block any public address.

## 12. Status — 20 Sep 2026: pacing the topic page (AC-U13)

From a redesign proposal the user brought (an illustrated "learning quest" mockup with XP, streaks and a "boss
battle"). Two of its ideas earn their place and were built; the gamification was declined against PRINCIPLES
§Tone and the §Measurement list, which names streaks as *not* a success metric. The mascot stays nameless: D5
says there is one assistant, the Tutor.

**What a page is made of** (`app/modules/learn/pacing.py`, a pure rule): the parts this page actually offers —
Learn, Check yourself, Exam questions — with minutes from the content itself (180 wpm for prose, two minutes a
worked example, about a minute a mark) and `done` from stored evidence (`explanation_viewed`, an attempt on one
of the page's items). A lessons-only subject shows one part. `TopicOut` carries `steps` and `minutes`; the web
header reads "Part 2 of 3 · about 16 min left" with a tick against what she has done.

**One page, one map.** The bar sticks to the top and each part jumps to its section, so practice is never
something she has to scroll to find; a taught topic always shows all four parts — Learn, Check yourself, Exam
questions, Your mistakes — with an honest empty line where there is nothing yet, because a part that hides
itself reads as a feature that does not exist. A lesson she has already read opens as its summary with the rest
one tap away (the page was three and a half screens; it is now one and a half). Questions are named by the API,
not the UI: "June 2025 · Paper 21 · Q17(b)(ii)" for a past paper and "Practice question" for a generated one,
in place of the internal key ("template / hcf_two_numbers / 0") the student used to see
(`app/modules/learn/labels.py`).

**Stepped worked examples** (`components/learn/WorkedExample.tsx`): steps are revealed one at a time, with the
answer shown once the working is complete and "Show all steps" for revision. No new content, no model call —
the steps were always stored; only the reading of them changed.

Not taken from the proposal: XP and streak counters, the countdown clock on practice questions (timing belongs
in timed sittings, which exist), a named mascot persona, and per-subject interactive sandboxes — the last is
possible only as deterministic widgets chosen by subject config, never drawn by a model, and is not scheduled.

## 13. Status — 20 Sep 2026: diagrams a lesson can carry (AC-U14)

**How it works.** `app/modules/learn/diagrams.py` holds ten kinds — `venn_factors`, `number_line`,
`bar_model`, `right_triangle`, `force_arrows`, `wave`, `coordinate_grid`, `straight_line_graph`, `ray_diagram`,
`circuit` — each a
Pydantic spec plus a check that *computes what is drawn*: the prime factors and the HCF/LCM, the resultant of
the arrows, the hypotenuse, v = f λ, the window and tick spacing of a pair of axes, and a line's own equation
("y = 1/2x - 2", written by SymPy so the label and the line can never disagree). The model's only job is to
pick a kind and give numbers (`lesson_illustrate/v1`, role `lesson_illustrator`, Flash-Lite). Lesson text is
never touched: `app.jobs.illustrate` runs over lessons that are already written and hand-checked.

**What the guard refuses**, learnt the hard way over four runs on 20 Sep: a kind the objective does not use; the
prompt's own example numbers (the model copied them, putting the same −5…5 number line on three unrelated
Physics topics); numbers the lesson never mentions; a caption whose numbers contradict the picture; a caption
copying the lesson; a bar model whose parts are called "Part 1" and "Part 2"; and arrows in amps, because a
current is not a force however neatly it draws.

**Which topic may carry which picture is curated in the subject config**, not decided by a model
(`pedagogy.diagrams: {venn_factors: ["1.5", "1.6"], …}`). That was the decisive change: asked to judge
relevance, the model put a wave on a thermal-energy lesson and a push-and-friction sketch on the motor effect.
A check can prove numbers; it cannot prove a picture belongs on a topic.

**And a person approves each one.** A stored diagram carries `approved: false` and is not served until
`app.jobs.illustrate --subject X --approve 6.1 8.4` marks it (`--review` lists candidates, `--reject` deletes).
Of 16 candidates across Maths and Physics, 5 were approved by hand and 11 rejected — the rejects included a bar
model whose total contradicted its label, and a transverse sine captioned "compressions and rarefactions".
Total cost of four full passes: under $0.02.

**The grid and the line graph** (20 Sep 2026) were added next, and share one set of axes so they look like the
same textbook: `coordinate_grid` plots points, optionally joined into a shape, for vectors and transformations;
`straight_line_graph` draws y = mx + c with its intercept marked, refusing any point that does not lie on the
line. Curated onto the graph and vector objectives (15.1–15.4, 29.x, 30.x). They doubled the yield at once: of
9 Maths candidates, 7 were approved — including y = 2x + 1 with (0, 1), (1, 3) and (−1, −1) marked, and a
vector drawn from (0, 0) to (2, 3).

**The ray diagram and the circuit** (20 Sep 2026) carry their own physics: a reflected ray leaves at the angle
it arrived; a refracted one follows Snell's law, with the angle inside the material and the critical angle
worked out here (45° into n = 1.5 gives 28.1°, critical angle 41.8°); a circuit's total resistance and current
come from the components and V = IR, in series or in parallel. Two more rules came out of the first run: a
circuit may not list the cell as a component (the model gave it 6 Ω, doubling the resistance and teaching that
a cell is a resistor), and these physical kinds are exempt from the "use the lesson's own numbers" rule,
because a refraction angle or a cell's voltage is illustrative and its own law already keeps it honest.

Two config decisions came from watching it fail: **sound (3.4) is deliberately left without a picture**, since
the wave drawing is transverse and a sine curve captioned "compressions and rarefactions" teaches the wrong
thing; and **the motor effect (4.5) was dropped from `force_arrows`** after the model drew push-and-friction
there three runs running.

Ten diagrams are approved across 211 lessons: three number lines, a bar model, two straight-line graphs, a
coordinate grid, a wave, a ray diagram and a circuit. The yield is deliberately low — most topics have no picture at all, which is the
right default. A ray diagram and a circuit would cover much of the rest of Physics.

## 14. Status — 20 Sep 2026: Explore with AI (AC-U15)

Asked for a button on each section that opens "more about this topic, with images and a video". Built as the
part that carries no new risk: a button on every lesson section that opens the **existing Tutor** in a panel,
with that section as the question. Nothing new asks a model to talk about a topic from general knowledge —
retrieval over her own books, citations, the copy check, the safety pipeline and the grounding label
("From your textbook" / "Based on limited material") all come along unchanged. The panel offers "Keep asking in
the Tutor" for anything longer.

That made the D4 amendment necessary: the button was drawn on a Physics page, and Physics had no Tutor. The
rule is now that **clearing a doubt works wherever Scholr explains a subject; setting and marking still need a
taught one** (`start_session` allows `mode: learn` for any subject that explains, and `prepare_explanation`
reads the explained config). Verified live on Physics 3.2, which answered from the Physics corpus and labelled
its own grounding.

Not built, at the user's decision (20 Sep 2026): **video references are deferred**, with Khan Academy the one
allowed channel when they come. When they do, they need the YouTube Data API with a channel allowlist, a check
that each video exists and is embeddable, privacy-mode embedding, and the same person-approval gate as the
diagrams — an LLM asked for a video link invents plausible ids. **Images stay as the diagram vocabulary**
(AC-U14) and, if it is ever built, cropped figures from her own books: no web image search, which would put
unvetted pictures and other people's copyright in front of her.

## 15. Status — 21 Sep 2026: "only the basics" — the exam level and lesson v4 (AC-U16)

**What she said.** After a few hours on 20 Sep 2026 she found the topics gave "only the basics". She was right,
and it was the design, not a bug: lesson prompt v3 asked for a *short* lesson (2–4 sections of ~150 words) to read
before practising, and the SymPy guard deletes any worked example it cannot check — which removes the harder
ones. 36 Maths lessons had no worked example at all. Maths 15.4 (solving equations graphically) taught straight
lines only, while every past-paper question on it is a cubic solved by drawing a line. The writer never knew:
it saw only the Collins section title. (That day she only read lessons; she attempted no questions.)

**The exam level (built).** A card on every taught topic, between the lesson and the questions:
- *How it's examined*: counted from the bank — "asked 6 times (2023–2025), Paper 2 and Paper 4, 1–4 marks,
  usually 'solve', 'by drawing'". No model.
- *A real exam question, solved* (Maths): one past-paper item per topic, picked by fixed rules (checkable
  answer, stands alone or is a graph question whose curve is stated, most marks, most recent), solved step by
  step from its mark scheme with each step's mark (M1/A1/B1), opened one step at a time, then what the examiners
  wrote about that question. `app.jobs.walkthroughs` writes them (Flash-Lite, prompt `exam_walkthrough/v2`,
  ~$0.001 a topic).
- The guard (`learn/exam.py`) came out of what the pilot actually produced. Flash-Lite drew the line
  y = x − 10 where the scheme's is y = 10 − x in three runs out of three, and once wrote "54 = 2 × 2 × 3 × 3"
  on the way to a right answer. So: the answer must pass the marking check (several-value answers matched line
  by line), marks must be the scheme's and not exceed the question's, every numeric equality is recomputed, a
  broken LaTeX escape rejects the step, and for graph questions the line is **computed by SymPy and given to the
  writer** (algebra is code's job), then every line the steps name is checked to solve the equation. It still
  cannot judge reasoning written in words (one run wrote a wrong rearrangement in prose), so **a person approves
  each walkthrough** (`--review`, `--approve`, `--reject`), as with diagrams.
- Coverage: 57 of 152 Maths topics with bank items have a question the rules accept; the rest need a figure we
  cannot show, or have no past-paper item. Sociology shows the count and says plainly that Scholr does not write
  its exam answers.

**Lesson v4 (piloted, not switched on).** `lesson_write/v4` tells the writer how the objective is examined (the
hardest past-paper questions on it) and asks for the whole objective to Extended standard: 3–6 sections, three
examples marked basic / standard / exam. Production still writes v3 (`learn.LESSON_PROMPT_VERSION`); the pilot
(`app.jobs.lessons --pilot … --prompt-version v4`) writes beside the stored lessons and saves nothing. Guard v7
came with it: examples and sections may not reuse a past-paper question (she tries those herself); a "solve"
example's answers are substituted back into its equation — the pilot produced "solve x² − 3x + 2 = x − 1 → 1.3,
2.7", which SymPy had passed because it only compared the answer with the model's own (wrong) expression; and
excerpt numbers written into the prose ("[1, 3]") are stripped. Recheck applied v7 to every stored lesson:
markers removed from 43, no stored example failed the new equation check. On Flash-Lite, v4 roughly doubles the
depth (15.4 now teaches the cubic method) but loses most exam-level examples to the checks.

**Switched on (21 Sep 2026, the user's decision).** The same five topics were piloted on `google/gemini-2.5-flash`
($0.033 for five): ~40% more than Flash-Lite, more exam-level examples kept (1.1, 11.1), exam technique taught
(state the line, plot it from a table, read to one decimal place), and Physics 4.4 kept two examples where
Flash-Lite kept none. The user chose 2.5 Flash for `lesson_writer` — the one exception to the Flash-Lite rule —
and a full rewrite with v4 (`LESSON_PROMPT_VERSION = "v4"`). Before it ran, the past-paper check was tightened:
both models had written a section combining one question's curve with another's equation, which no run of words
matched, so sections and examples are now also refused when they write the same polynomial curve or equation as a
past-paper question (SymPy, up to a constant factor). A rewrite replaces the lesson text, so its diagrams (tied to
the old sections) go with it; they are offered again by `app.jobs.illustrate` and need approving again.

## 16. Decision — 21 Sep 2026: her voice stays inside Scholr's own pipeline

Another session added voice input to the Tutor using the browser's speech recognition. In Chrome and Edge that
sends her recording to Google or Microsoft under their terms — outside `provider_preferences` (no data
collection), with no record in `llm_call`, for a minor. The user chose to replace it:

- **Recorded on her device**, converted there to a 16 kHz mono WAV (`web/src/lib/voiceRecorder.ts`), at most 60 s,
  and sent once to `POST /tutor/speech` with her normal sign-in.
- **Checked by code first** (`tools/wav.py`, `tutoring/speech.py`): a real PCM WAV, 0.3–60 s, under 4 MB — or a
  400/413/422 with no model call.
- **Transcribed through the gateway**: role `speech_to_text` on `gemini-2.5-flash-lite` (the Flash-Lite rule holds;
  it takes audio directly), prompt `speech_transcribe/v1`, provider preferences sent, recorded with its cost
  (~$0.0001 a question). It transcribes only — British spelling, maths written as she would type it
  (`x^2 - 5x + 6 = 0`) — and marks guessed words as `unclear`.
- **Nothing is stored**: not the recording (no file, no row, no log), and not the text until she sends it.
- **She checks it**: the text goes into her message box with "Check what I heard, then press Send"; a sent message
  goes through the normal turn and its safety checks like anything typed.

The browser's speech recognition is gone from the code. The same review moved lesson read-aloud (`lesson_voice`,
Kokoro 82M) behind the gateway with a recorded per-character cost, and stopped the API accepting a sign-in token
in the URL.

## 17. Decision — 21 Sep 2026: two models only, batch where possible

The user's rule, replacing the Flash-Lite-only rule of 19 Sep: **only Gemini 2.5 Flash-Lite and GLM 5.3 Flash**, no
other LLM, no fallbacks. GLM 5.3 Flash takes the place of Gemini 2.5 Flash, for lesson writing and the solved exam
questions; Flash-Lite does everything else. The two non-LLM models stay, by the user's decision: Kokoro 82M
(read-aloud) and bge-m3 (the embeddings that let lessons and the Tutor search her books).

**Batch and live.** The user asked for the `:batch` variants. OpenRouter serves those only through its Batch API:
requests are submitted together, results come back within 24 hours, with no streaming and no inline images or
audio. So each role names a live `model` and, where it has a batch job, a `batch_model`:

| | live (`model`) | batch (`batch_model`) |
|---|---|---|
| lesson_writer, exam_walker | `z-ai/glm-5.3-flash` | `z-ai/glm-5.3-flash:batch` |
| lesson_illustrator, summarizer, examiner_report_extractor | `google/gemini-2.5-flash-lite` | `google/gemini-2.5-flash-lite:batch` |
| every other role (Tutor, marking, OCR, voice, safety…) | `google/gemini-2.5-flash-lite` | — |

`tests/unit/test_ocr_roles.py` enforces the table. The lessons, walkthroughs and illustrate jobs submit through the
gateway's `batch_submit` / `batch_collect` (`app/jobs/batching.py`; `--live` for one-off calls, `--resume` to collect
a batch an interrupted run left behind). Each reply is checked against its schema and recorded in `llm_call` with
its own cost; an unreadable reply is queued once more, then reported as failed — never sent to another model.
A lesson written the first time she opens a topic is live, on GLM 5.3 Flash.

**What the first runs showed.**
- GLM 5.3 Flash always reasons and cannot switch it off. Unchecked, it wrote ~13k characters of thinking and hit
  the token cap before any JSON (27 of the first 28 batch walkthroughs). Both GLM roles now send
  `reasoning: {effort: low, exclude: true}`; with it, a live pilot wrote 3 of 4 lessons at about the depth of the
  2.5 Flash ones (1.6, 11.1, 1.1; 15.4 still failed its schema twice).
- A batch took ~11 minutes for 28 requests ($0.0105).
- **Data policy.** The Batch API accepts only `provider.only`, so the per-request `provider_preferences`
  (`data_collection: deny`) cannot be sent with a batch; the OpenRouter account's own privacy setting applies.
  That setting must disallow providers that store or train on prompts. Batches carry lesson material and past-paper
  text, never her answers or messages — every student-facing call is live and sends the preference.
- Stored lessons stay as written by 2.5 Flash; GLM writes new ones and any rewrite from here on.

## 18. Status — 22 Sep 2026: Chemistry and Biology lessons (step 6)

At the user's request ("complete Physics, Chemistry and Biology lessons topic wise"). Physics already had all 24.
Chemistry and Biology moved from `planned` to `lessons` — grounded lessons and the Tutor for doubts; nothing set or
marked (Chemistry marking needs the equation balancer and mole checks first; docs/ROADMAP.md).

- **OCR.** Both coursebooks are scans with no text layer: 957 pages on `page_ocr_math` / `page_ocr_math_md` at
  220 DPI (the Collins settings), live Flash-Lite (the Batch API takes no inline images), ~$0.55. The "2001 edition"
  Biology book is in fact the current Cambridge IGCSE Biology Coursebook; its manifest is corrected.
- **Printed pages.** Markdown OCR does not report page numbers, so `label_text_layer_pages` now labels any
  unlabelled page (offsets: Chemistry 12, Biology 10) and runs after every OCR.
- **Objectives to pages.** Each curriculum file gained `pages:` from the book's contents pages and, where two
  objectives share a section, the section's headings in the OCR text. Biology 15.1 (Drugs) has no section in the
  book, so it has no pages.
- **Tagging across a span.** Chunks follow headings, so a long section with none (Chemistry 13.2, pp. 261–266) made
  chunks that all carried its first page, and Group I and Group VII got nothing. A chunk now belongs to every
  objective that starts inside its pages (`chunking.sections_for_span`).
- **Retrieval.** When a search is scoped to objectives, their own chunks are also ranked by vector distance, so the
  pages a topic is taught on are measured rather than found by keyword only (Biology 1.1 and 4.1 went from LOW to
  HIGH/MEDIUM). Thresholds unchanged; the retrieval eval is unchanged (recall@8 0.97, state agreement 1.0, pass).
- **Lessons** on the GLM 5.3 Flash batch (§17), $0.083 for 106: **Chemistry 48 of 49, Biology 60 of 61.** Not
  written, honestly: Chemistry 3.1 (Formulae — its pages match at ~0.50, below the bar) and Biology 15.1 (Drugs — not
  in the book). The guard dropped 65 sections that copied the book and 27 Chemistry examples whose answer SymPy or
  Pint could not confirm.
- **Rendering.** Guard v8 wraps maths written outside `$…$` ("H_2O", "12x^3", "10^23") so it renders — chemistry and
  units upright — applied to 21 stored lessons.

