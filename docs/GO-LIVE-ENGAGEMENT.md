# Going live, and coming back tomorrow — review and plan

**Status:** proposal, 25 Oct 2026. Nothing here is approved. CLAUDE.md says anything outside
`docs/PHASE-1.md` needs the user's explicit approval, and several items below are exactly that.
**Audience:** IGCSE first (the student sitting Sociology 0495 in May/Jun 2027 and Maths 0580 in 2028);
IIT Foundation stays `external` and is treated as a schedule and a bridge, not a taught course.
**Start at §4** for the twelve improvements. §3 is what has to be repaired first; §5 is what the features
stand on.
**Read with:** `docs/PRINCIPLES.md` (wins every conflict), `docs/STUDENT-APP.md` (what is built), `docs/PHASE-1.md`.

---

## 1. Where the product actually stands

The engine is further ahead than the app's own surface. It is grounded in her own books, checked by code, with
a person approving anything a model drew or solved:

| Built and honest | Evidence |
|---|---|
| Lessons over her own textbooks, cited page by page, guard v9, SymPy/Pint-checked examples | 211+ lessons across Maths, Sociology, Physics, Chemistry, Biology |
| Verified question bank from real past papers, mark-scheme parsing, examiner insights | Maths: 469 servable questions, four series |
| Marking (`structured_math`, `essay_levels` dual marking), mastery v1 from append-only events | `modules/evaluation`, `modules/mastery` |
| Daily practice set chosen by rule, with a reason on every question | `GET /practice/daily`, `planner/daily.py` (`daily_set_v1`) |
| Tutor everywhere, grounded, with server-side voice inside our own pipeline | `modules/tutoring`, `tools/wav.py` |
| Walkthroughs, Bug Hunter, Crucible, viva — all built on approved, checked sources | `learn/exam.py`, `mistakes/challenges.py`, `learn/crucible.py` |
| Accounts with admin approval, home-machine deploy, installable on her phone | `AUTH_MODE=local`, `infra/docker-compose.home.yml` |

**What is weak is everything between signing in and doing the work**, plus a layer of recently added UI that
does not meet the project's own bar. The web app type-checks clean (`tsc --noEmit`) and there are 102 API test
files — the problem is not stability, it is honesty of surface and the cost of her attention.

---

## 2. The engagement question, answered inside the principles

The ask is daily return. `docs/PRINCIPLES.md` is explicit that streaks, screen time and conversation volume
are **not** success metrics, that gamification stays minimal, and that long-term learning beats short-term
engagement. That is not in conflict with daily return — it rules out one *way* of getting it.

**What we will not build:** XP, points, levels, badges, streak flames, loss aversion ("your 12-day streak will
die!"), leaderboards, variable rewards, or any counter that rises for time spent rather than learning done.
This was already declined once (STUDENT-APP §12) and the decision stands.

**What actually makes a 15-year-old open a study app on a Tuesday night**, in the order the evidence supports:

1. **It is obvious what to do, and it is small.** One action, under ten minutes, already chosen for her.
2. **The loop closes the same day.** She answers, it is marked, she sees what an examiner would say.
3. **The content is worth her time.** Her own words, 20 Sep 2026: the lessons gave "only the basics", and
   "reading just text is so inconvenient". v5/v6 answer that; coverage has to follow.
4. **Something reminds her, at a time she chose.** This does not exist today. It is the single biggest lever.
5. **Progress is visible and true.** Not a percentage that flatters — the exam getting closer and her gaps
   getting fewer.
6. **A person notices.** A parent asking at dinner about the Crucible debate beats any badge.

The honest substitute for a streak is **rhythm**: "you studied 4 of the last 7 days, with Sunday off" — already
computed in `WeekOut.active_days`, never framed as a reward, never punished when she rests.

---

## 3. Blockers — fix before anyone calls this live

Not polish. Each one breaks a rule the project already wrote down.

### B1. Invented content presented as fact

`apps/web/src/app/student/examinations/strategy/page.tsx` is hand-written exam advice with fabricated numbers:
"Syllabus knowledge gets you 70%", "Target: 45–50% of marks in 35% of clock time". No source, no examiner
report, no mark scheme. That is PRINCIPLES §9 (never invent) and §29 (no mock intelligence in production
paths). **Fix:** rebuild it from attributed examiner reports (we already extract those, AC-R6) and from her own
`readiness` data, or delete the page. Nothing in between.

### B2. Hard-coded student data on the home page

`apps/web/src/app/student/page.tsx` prints an IIT timetable as literal strings — "MON · Biology (19:00)",
"THU · Physics & Chemistry", "SAT · Mathematics (17:30)". CLAUDE.md forbids hard-coding student data outside
seed files, and the times are also **wrong**: her record has the Monday class at 16:30, not 19:00. (Running
the app on 25 Oct 2026 showed the seeded record does hold an IIT Biology class, which `docs/CONTEXT.md` does
not list — so the subject was right and this section's first version was wrong to say otherwise; §13.)
**Fix:** read it from the household seed, or show nothing.

### B3. A competitor's brand name inside the product

"SaveMyExams" appears in seven web files, including the sidebar, the home copy and the filename
`components/learn/SaveMyExamsQuestions.tsx`. We are describing our own feature with someone else's trade mark.
**Fix:** rename it to what it is — **Topic questions**, graded *Easy → Medium → Hard*.

### B4. The assistant has three names again

D5 settled on one assistant called **Tutor**. The shipped UI says "AI Academic Mentor" and "AI Mentor"
(`AppShell.tsx`, `student/page.tsx`, `AskBox.tsx`, `demo/page.tsx`). PRINCIPLES §UX also rules out AI jargon.
**Fix:** Tutor, everywhere, once.

### B5. Business logic and subject names inside React

`SaveMyExamsQuestions.tsx` (1,123 lines) branches on `subjectCode === "igcse-maths"` / `"igcse-sociology"` to
invent difficulty tiers and "coaching help" in the browser, and keeps her self-scores in `localStorage`. That
breaks three conventions at once: no business logic in components, no `if subject ==` outside config, and
anything that counts as evidence must be a `learning_event`, not a browser key she loses when she clears her
cache. **Fix:** difficulty from the bank and the subject config, served by the API; self-marking either becomes
a real event or goes away.

### B6. Tone and sprawl

"Command Center", "Executive Overview", "Safety Telemetry", "ANALYTICAL TELEMETRY STRIP", a "LIVE" badge that
means nothing, and fifteen student destinations in the sidebar. PRINCIPLES §UX asks for calm, uncluttered,
age-appropriate. This reads like a trading desk. **Fix:** §5.1.

### B7. Safety notifications and helplines (U4, U5)

Deferred by the user (D8). They block any **public** address, not home use. Nothing here changes that — but if
"live" means a VPS and a URL, these come first.

### B8. A large unreviewed working tree

138 changed paths: 89 tracked files (+6,034 / −1,807) plus untracked features — `student/notebooks`,
`student/examinations`, `demo/`, bookmarks, `assessment/analytics.py`, two migrations. Most of the problems in
this section live in it. **Fix:** review, repair and commit it in slices before building anything new. Going
live from an uncommitted tree is not a plan.

### B9. The validation study is running right now

Phase 1's study (AC-P2: control topics get no lesson and no practice) is mid-flight — Maths post-test was W8,
retention W11, gate 21 Dec 2026. Any change to navigation, reminders or feedback affects both arms and muddies
the measurement. **Fix:** date every change below in the study log, and let the reminder work (§5.2) wait for
the crossover unless the user decides the engagement risk outweighs the measurement.

---

## 4. Improvements — the twelve things worth building

Twelve features, in the order I would build them. Each says what it is, **why she opens the app because of
it**, what it already stands on, and what is missing. Almost all are deterministic: of the twelve, one calls a
model (F3, about $0.001 a photo). The engine for these is already paid for — what is missing is the feature on
top of it.

**If you only pick three: F1, F3 and F5.** F1 gives the day a shape, F3 ties the app to something that happens
to her every school day, and F5 tells her what her effort is worth. F7 is the cheapest delight on the list.

### F1. "Today" as a thing that finishes

A named, fixed, small set — five or six questions — with a visible **end**. Today's set already exists
(`GET /practice/daily`); what is missing is closure. The page never says "that's today done", so there is no
moment of finishing, and no reason to come back for the next one. Add the done state, and one line of what
tomorrow holds ("tomorrow: four on Trigonometry, from Thursday's class").

*Stands on:* `planner/daily.py`, `reasons.yaml`, the pacing minutes. *Needs:* a done state and a tomorrow
preview (topics, not questions — the set is chosen on the day). *Why she returns:* a task with an end is a task
you can face on a Tuesday. The finish is the reward; nothing is scored.

### F2. "I've got ten minutes"

Three doors instead of one: **3 minutes** (one question on something fading), **10 minutes** (today's set),
**25 minutes** (one topic, lesson through to questions). The minutes are already computed per page by
`learn/pacing.py`.

*Needs:* the three entry points, and the set trimmed to the size she picked. *Why she returns:* "I haven't got
time to start" is the most common reason a teenager doesn't open a study app on a weeknight. This removes it.

### F3. Photograph your homework, land on the right topic

She is set school homework most days. She photographs the worksheet; we OCR it with the same roles that read
her textbooks, match the text against the objective embeddings already in the index, and offer her the topic —
then the lesson, the three bank questions on it, and the Tutor scoped there.

*Stands on:* `PhotoAnswer`, the OCR roles, `jobs.knowledge search`, bge-m3 over the curriculum. *Needs:* one
endpoint (photo → candidate objectives) and a confirm step: she picks, we never assume. *Why she returns:*
**this is the strongest daily hook on the list.** It makes Scholr the thing she opens *because of* school
rather than in addition to it — her homework is the daily trigger, and we supply the response. *Care:* it
routes into the help ladder, never into an answer. It coaches her through her own homework; it does not
produce it (PRINCIPLES §18, §27).

### F4. "What did you do in class today?" — one tap

One question each school day, two taps to answer: which topic each subject covered. From it: "Sociology did
Identity today — eight minutes to lock it in", that same evening, when retention is cheapest.

*Stands on:* `teaching_plan` and `GET /teaching-plan`; the term topic lists are already seeded. *Needs:* the
tap, stored as her own record. **And it quietly answers U2** — the week-by-week scheme of work nobody has,
which has been blocking validation topic selection since W4. She builds it by using the app. *Why she
returns:* it is tied to an event that happens five days a week and takes five seconds, which makes it the
cheapest habit on this list to form.

### F5. The marks ledger — what your next hour is worth

For every objective: how often it has appeared in past papers, times the marks it carried, against the gap in
her evidence. Put in her language — *"these three topics carried about 18 marks across the last four Paper 2s,
and you have no evidence on any of them."*

*Stands on:* the bank's per-objective counts (already counted for the exam-level card), mastery projections,
`readiness`. **No model** — this is arithmetic over rows. *Needs:* one deterministic service, and the readiness
screen (§5.5) to show it on. *Why she returns:* agency. A fifteen-year-old who can see what her next hour is
worth will spend it. Labelled as past frequency, never as a prediction of this year's paper.

### F6. Mistakes that visibly close

Every open mistake gets a sibling question — a template item for Maths, a bank item elsewhere. Get it right and
the mistake **closes**, with a ledger of what she has fixed this month.

*Stands on:* the mistake bank, `jobs.templates`, and PRINCIPLES §19, which already requires success on a
similar item before credit. *Needs:* the sibling-picking rule and the repair screen. *Why she returns:* a list
that shrinks pulls harder than a score that grows, and here the shrinking *is* the learning.

### F7. One slip a day

Bug Hunter already builds a challenge from an approved walkthrough with exactly one SymPy-verified slip in it.
Make it **today's**: one, new each day, two minutes.

*Stands on:* `mistakes/challenges.py` — 15 challenges from the 48 approved walkthroughs. *Needs:* a day-stable
pick, and more approved walkthroughs; the supply is the constraint, not the code. *Why she returns:* a puzzle a
day is the most reliable daily-return format there is, and this one is pure exam skill — spotting the error in
worked maths is what an examiner does. No points, no streak, no flame: just today's puzzle.

### F8. Two minutes of talking

The viva, on-device recording and server-side transcription are built. On a phone, talking is far less friction
than typing maths. One step of one question, explained out loud, judged against that step only.

*Stands on:* `learn/viva.py`, `tutoring/speech.py`, the approved walkthroughs. *Needs:* a phone-shaped screen
for it. *Why she returns:* it is quick, it is unlike anything else she does all day, and explaining out loud is
the highest-yield study act there is.

### F9. Lessons she can listen to, in the car

Read-aloud already runs through the gateway (Kokoro). With the service worker from §5.2, a lesson and its audio
can be cached and played offline.

*Needs:* the service worker, a cache policy, a download control. *Why she returns:* a second modality creates
sessions that could not otherwise exist — the commute, the bus, ten minutes before sleep. It does not compete
for screen time; it uses time that was empty.

### F10. Flashcards made of her own errors

`ActiveRecallDeck` and the notebooks exist. Build the deck from **her** mistake bank and the key terms of
lessons she has actually read, ordered by what is fading.

*Needs:* card generation from existing rows (no model) and ordering by retention risk. *Why she returns:*
thirty seconds a card, phone-shaped, and visibly hers rather than generic.

### F11. The Crucible as a weekly fixture

An approved debate per Sociology topic, from her own coursebook, placed deliberately **before** the class that
covers it — and its question handed to the parent dinner-starter card.

*Stands on:* `learn/crucible.py`, `DinnerStartersCard`. *Why she returns:* one anticipated thing a week, and a
conversation at home that is about the subject rather than about whether she has studied.

### F12. Ten minutes on Sunday, with a parent

A weekly review built to be opened *together*: what she fixed, what is fading, what is next, and this week's
Crucible question.

*Stands on:* `WeekOut`, the focus list, `recent_wins`, the guardian monthly summary. *Why she returns:* at
fifteen, external accountability beats internal motivation — and a parent noticing is the mechanism PRINCIPLES
already prefers over a badge.

### Deliberately not recommended yet: a predicted grade

It is the most motivating single number a student can see, and I would still wait. An honest one needs enough
marked held-out past-paper work to stand on (PRINCIPLES §16 asks for independent evidence), and Sociology
cannot produce one at all while its evaluator is uncalibrated (U3). A predicted grade built on thin evidence is
a guess she would believe. Revisit once she has sat two or three full papers.

### For IIT Foundation students

Nothing separate, and nothing that teaches the IIT syllabus (PHASE-3 §1). The three classes a week are three
guaranteed sessions if we use them: the **warm-up** before class exists already, F4's one tap becomes the class
log, and a five-minute **debrief** after it ("what was hard?") feeds the ground-underneath trace that is also
already built. That is Monday, Thursday and Saturday accounted for, by complementing the classes rather than
competing with them.

---

## 5. Foundations the features need

The five below are not features she would name. They are what every feature in §4 stands on: one clear
next action, a way to be reminded, feedback that arrives, content worth reading, and the exam in view.

Each is written to the project's definition of done (API + logic + events + tests + evals + UI), and each has
an acceptance criterion that can fail.

### 5.1 One door, one next action

Today she signs in to a hero banner, a four-tile telemetry strip, two practice cards, three streams, a
timeline, a subject grid, a toolkit grid and three right-hand cards — plus fifteen sidebar links. Every one is
a decision she must make before she learns anything.

- **Home becomes one card:** today's single next action (from the plan, else the daily set, else the topic she
  left), with its reason, its length in minutes, and one button. Everything else moves below the fold.
- **Resume:** the last topic, question or sitting she had open, from her own events — "You were on 13.3, three
  questions left."
- **Sidebar from fifteen to five:** Today · Subjects · Practice · Tutor · Progress. Mock exams, past papers,
  notebooks, error log, strategy and IIT live *inside* those, where they belong.
- Names a student uses: *Today*, *Subjects*, *Practice*, *Tutor*, *Progress*, *Mistakes*. Not *Command Center*,
  not *Telemetry*.

**AC-E1** From sign-in, the first action is one tap away, and home makes no request whose failure blanks the
page. **AC-E2** Resume is computed from `learning_event` only; with no history it says so plainly.

### 5.2 A reminder she chose — the missing lever

There is no study notification anywhere in the product. `app/jobs/notify.py` delivers **safety** incidents
only, and the PWA has a manifest but **no service worker**, so no push and no offline reading.

- A service worker with Web Push, and a `notification_preference` row she owns: on/off, one or two times a day,
  quiet hours, and an off switch honoured without argument.
- Content specific, never guilt-based: "Today's set: 5 questions, about 12 minutes — 2 on last week's
  mistakes." Never "you haven't studied in 3 days", never a streak at risk.
- A job in the existing Postgres scheduler (no Redis, no Celery) builds the day's set before the reminder
  fires, so the app is ready when she opens it.
- One reminder a day by default; two is the maximum the schema allows.

**AC-E3** No notification is ever sent to a student who has not switched it on; the preference is per student
and audit-logged. **AC-E4** A reminder names a set that exists at send time, or is not sent. **AC-E5** Quiet
hours and school hours (from the planner) are respected with no exception path.

### 5.3 Close the loop the same day — Sociology is the problem

Maths closes in seconds: SymPy marks it. Sociology does not. Every Sociology mark goes to parent review because
the evaluator is `calibrated: false` (U3 — we still have no teacher-marked answers). So she writes a 15-mark
answer and gets **nothing back until a parent sits down with it**. For the subject whose exam is seven months
away, that is the strongest reason she has not to come back.

Two options, and this is the user's call:

- **(a) Provisional feedback, no mark.** She immediately sees which mark-scheme points her answer hit and
  missed, and the AO bands, labelled *provisional — waiting to be checked*. No number, no mastery change
  (PRINCIPLES §13 holds), parent review queue unchanged.
- **(b) Answer U3.** Ten to twenty teacher-marked Sociology answers calibrate the evaluator and the problem
  disappears. The better fix, and it needs a person, not code.

Do both: (b) is the goal, (a) is what she lives with until it lands.

**AC-E6** A provisional view never shows a mark, a grade or a band total, never emits an evaluation that
mastery reads, and says in one line who will check it and when.

### 5.4 Content worth opening — finish the subjects

She told us the lessons were thin. The structural answer (v5: definitions, bullets, tables, exam tips, model
exam answers, drawn pictures) is piloted on Chemistry chapter 2 only. Nothing brings a student back like the
page being good.

- Roll v5/v6 across Maths and Sociology (batch, GLM 5.3 Flash — cost in the tens of cents).
- Close the honest gaps: 7 Maths topics at `not_enough_material`, Chemistry 3.1, Biology 15.1 (not in the
  book). Either find the material or keep saying so — never fill it from the model.
- The 36 Maths lessons with no worked example: v4+ raised the depth; recheck which are still empty.
- Walkthroughs reach 57 of 152 Maths topics with bank items. Most of the rest need a figure we cannot show —
  say so on the page.
- Diagrams: 10 approved across 211 lessons, and the new Chemistry kinds are unreviewed. A ray diagram and a
  circuit would cover much of Physics. This is a **human approval queue**, not a job (§8 D-E6).

**AC-E7** No lesson is served that the current guard version would reject; a rewritten lesson's diagrams are
re-approved before they are shown again.

### 5.5 Show her the exam, honestly

`GET /subjects/{id}/readiness` already exists — evidence by topic, by command word, by paper, and days to the
exam — and **the web app never calls it**. This is the third finished API to ship without a screen
(STUDENT-APP §8 found the same for sittings).

- A readiness page per subject: days to May/Jun 2027 (Sociology) and 2028 (Maths); topics with evidence against
  topics without; command words where she loses marks; papers sat.
- No confident zero: a topic with no evidence says *no evidence yet*, never 0%.
- One button out of it: practise the weakest thing — which is the next day's return trip.

**AC-E8** Every number on the readiness page traces to events or the bank. Nothing modelled, nothing
extrapolated.

---

## 6. Sequence

| Wave | What | Why now |
|---|---|---|
| **W-0 (this week)** | B8 review and commit the tree; B1 strategy page; B2 hard-coded timetable; B3 rename; B4 Tutor | Rule breaches, cheap to fix, and everything else sits on top of them |
| **W-1** | §5.1 one door and the five-item nav; **F1** today finishes; **F2** three session sizes; B5 logic out of the question component; B6 tone pass | Biggest attention win, no new subsystems, and F1/F2 are the same screen |
| **W-2** | §5.5 readiness screen with **F5** the marks ledger; §5.3(a) provisional Sociology feedback; ask the user for U3 | The exam is the real motivator; Sociology feedback is her biggest dead end |
| **W-3** | **F3** photograph your homework; **F4** one tap on today's class | The two features tied to her actual school day; F4 also answers U2 |
| **W-4** | §5.4 content: v5/v6 rollout, coverage gaps, approval runs; **F7** one slip a day and **F6** mistakes that close | Content runs on batch in parallel; F7 needs the approval queue moving |
| **W-5** | §5.2 service worker, push, preferences — **after the study crossover, or on the user's explicit decision** — then **F9** offline listening on the same plumbing | The change that touches the validation study hardest; F9 is nearly free once the SW exists |
| **W-6** | **F8** the viva on a phone; **F10** flashcards from her errors; **F11** the Crucible as a fixture; **F12** Sunday with a parent | The rhythm pieces, once the daily loop holds |
| **Later** | B7 safety notifications and helplines, HTTPS, VPS; a predicted grade only once she has sat two or three papers | Only needed for a public address, or for evidence we do not have yet |

IIT Foundation: nothing that teaches its syllabus. F4's tap becomes the class log and a five-minute debrief
after each class feeds the trace that is already built, which accounts for Monday, Thursday and Saturday
(§4). Teaching IIT Maths (D2) still waits for a verified IIT question bank, as agreed.

---

## 7. How we will know it worked

North star stays **Learning Progress per Hour** against held-out assessments (PRINCIPLES §5). Engagement is a
*leading indicator*, reported beside it and never instead of it:

| Measure | Read it as | Not as |
|---|---|---|
| Active days per week (`WeekOut.active_days`) | rhythm | a streak to defend |
| Days the daily set was finished | the loop closing | a quota |
| Median time from sign-in to first answered question | friction | speed |
| Answers reached with no help (`answers_without_help`) | independence | difficulty |
| Open mistakes repaired, retention queue depth | learning | activity |
| Reminder opt-in and opt-out rates | consent working | growth |

A red line, written down in advance: **if active days rise while independent-solve rate or held-out gains fall,
the engagement work is making things worse and gets rolled back.**

---

## 8. Decisions needed from the user

| # | Question | Blocks |
|---|---|---|
| D-E1 | Approve §4 and §5 as scope beyond `docs/PHASE-1.md`, or pick a subset | all of §4–§5 |
| D-E2 | Reminders (§5.2): before the validation crossover, or after the 21 Dec gate? | W-4 |
| D-E3 | Sociology provisional feedback (§5.3a) — acceptable, or wait for calibration? | W-2 |
| D-E4 | U3: can we get 10–20 teacher-marked Sociology answers? | Sociology marking, ever |
| D-E5 | Does "live" mean the home machine, or a public URL? A URL pulls U4/U5 and HTTPS forward | B7 |
| D-E6 | Who runs the diagram and walkthrough approval queues, and how often? | §5.4 |
| ~~D-E8~~ | ~~Availability on IIT days~~ — answered 26 Oct 2026: leave it, those evenings are full | — |
| D-E10 | The four Flash-Lite roles still name a `batch_model` OpenRouter withdrew: drop the line, or keep it and always pass `--live`? (§17) | every Flash-Lite batch job |
| ~~D-E11~~ | ~~Guard tagging by paper section~~ — done 27 Oct 2026 (§19) | — |
| ~~D-E12~~ | ~~Seven questions tagged outside their unit~~ — six retagged 28 Oct 2026 (§20) | — |
| ~~D-E13~~ | ~~The old-format theory question~~ — moved to 2.2 on 28 Oct 2026, declared in the manifest (§20) | — |
| ~~D-E9~~ | ~~A full evening on home~~ — answered 26 Oct 2026: lead with the quiet day, offer the set quietly (§15) | — |
| ~~D-E7~~ | ~~`/demo` — delete it, or move it out of `src/app/`?~~ Answered 25 Oct 2026: moved to `design/mockups/` | — |

---

## 9. Status — 25 Oct 2026: W-0 blockers B1–B4 done

Not committed: the working tree still holds the unreviewed work of B8, and these fixes sit inside it.

- **B1** `student/examinations/strategy/` deleted, with its three entry points (sidebar, home strip, mock-exam
  header). Beyond the figures named above, it also claimed "1.2 minutes per mark" where the app's own pacing
  rule uses about a minute a mark, and coached "14-markers" where 0495's top band is 15. What it tried to be
  returns in §5.5 from `readiness`; what a command word asks for is already served per question from the
  subject config with its source named (`CommandWordRubric`).
- **B2** The home strip now reads `GET /commitments` — her own record, which the household seed fills — and
  renders each one's days from its recurrence rule (`commitmentDays` in `lib/format.ts`, pure, with a test
  worth adding). With no commitments the strip does not render. It no longer names a stream, which AC-U1 asks
  of UI code, so it reads "Your weekly classes" and covers sport and school hours too.
- **B3** `SaveMyExamsQuestions.tsx` → `TopicQuestions.tsx`, export and all copy with it. The two
  `localStorage` keys keep their old names on purpose, so nothing she has saved is dropped; B5 replaces them
  with events. The component's subject branching and in-browser difficulty tiers are untouched — that is B5,
  and it needs API work.
- **B4** One assistant, called **Tutor**: the sidebar, the mobile bar, the home card, the Tutor page's own
  heading and the search placeholder. The consent page had been telling her the assistant was an "AI Study
  Companion" and "mascot buddy" — it now says Tutor, which is what D5 decided and what she sees everywhere
  else. The guardian's "Mentor Notes" is "Learning Notes".
- **`/demo` is out of the app** (D-E7 answered 25 Oct 2026: move it, don't delete it). The 1,325-line mockup —
  theme presets named after ALLEN Overseas, Bhanzu and SaveMyExams, with invented sample questions, marks and
  progress — now sits in `design/mockups/senior-studio.tsx` beside the other design files, with a README
  saying what it is. Outside `apps/web`, so the route table and `tsconfig` never see it: `/demo` was a page any
  signed-in account could open, and is not a route any more. The layout ideas are kept; the names and the
  sample data do not come back into the product.
- **Two more found while clearing `/demo`,** both fixed: the header's theme switcher was labelled
  "🏛️ ALLEN Pro" (a visible button, not a comment), so the preset is now `light` / `dark` — the CSS only ever
  keyed on `dark`, so nothing else moved; and `tests/e2e/student-journey.spec.ts` still asserted a link named
  "AI Companion", the name D5 retired on 19 Sep, so it now looks for the Tutor. Section comments naming
  another product are gone from the eight files that ship. No competitor name and no earlier name for the
  assistant survives anywhere under `apps/`.
- **Verified by** `tsc --noEmit` clean and a full `next build` clean, with `/demo` and the strategy route gone
  from the route list, and by reading `rbac.can_access_student` to confirm a student principal may call
  `/commitments` for herself. **Not verified in a browser, and the e2e suite was not run:** both need the dev
  database up, and her dev DB is her real record.

---

## 10. Status — 25 Oct 2026: F1 built

**The finish.** Today's set now ends. When every question in it has been answered the page opens with
"That's today's set done", the count and the minutes she actually spent answering (timed by the answer box,
nothing estimated), and a line for any answer still waiting for a parent's check. No points, no streak, no
badge: the end of the day is the point.

**Tomorrow's preview.** Under it, up to three topics tomorrow will start from, each with the reason the
planner would give. It runs the **same rule** (`daily.choose`, `daily_set_v1`) over her record as it stands,
so it is not a second opinion:

- Tomorrow's plan is not generated, because generating it would write rows for a day that has not started.
  So the preview uses her *state* wants only — open mistakes worst first, retention risk, then topics she has
  only read. `_daily_wants` is now `_plan_wants` + `_state_wants` for exactly this.
- A topic is named only if it still has a question she has not answered inside the rule's 14-day window, so
  the preview cannot promise work that is not there. Nothing waiting means it says so instead.
- The page says plainly that tomorrow is chosen in the morning and can change.
- It is computed only once the set is finished — the one place it is shown — so an unfinished day costs
  nothing extra.

**Tests.** Two unit tests on the rule at preview size, two integration tests on the endpoint: nothing
previewed while work remains, the preview naming a topic she has only read, one line per topic, the order of
claim held, and a topic whose questions she has just answered left out. 847 pass; `tsc` and `next build`
clean.

**Two things worth knowing.** My first two integration tests asserted the preview would name *only* my
fixture's topic; they failed because the seeded household already has other claimed topics with bank items.
The feature was right and the test premise was wrong, so they now assert properties that do not depend on
what the seed contains. And `infra/docker-compose.yml` still defines a Redis container, which failed to start
on a port already in use; Phase 1 wants no Redis (CLAUDE.md), the database came up fine and nothing here uses
it, but the service should probably go.

**Not verified in a browser.** The finish panel renders only when every question in a real set is answered,
and submitting answers as her writes real, append-only events into her record. The integration tests exercise
that path against the test database instead.

---

## 11. Status — 25 Oct 2026: F2 built

**Three doors, on the home page.** "How long have you got?" — *A couple of minutes*, *Today's set*, *One topic,
properly* — each showing what it actually takes, from its own content: about a minute a mark for questions
(`learn.pacing`, the examiner's rule of thumb), and for the long door the topic page's own estimate of what she
has left.

**The long door cannot disagree with the page it opens.** `learn.remaining_minutes` reads the same
`topic_view` the page is built from and sums the steps she has not done, so the door and the header can never
print two different numbers for the same topic. An integration test asserts they match.

**The budgets are targets, not labels.** `sessions.QUICK_MINUTES` is 3, and the short door fills itself with
her shortest unanswered revision questions while they fit. If the only thing due is an 8-mark question it is
still offered — showing "about 8 min", because a door that lies about five minutes is worse than one that
admits to them. That rule is pure and unit-tested (`planner/sessions.py`, 7 tests).

**A closed door stays visible with its reason** ("Nothing is due for revision today", "You've finished today's
set"), which is the call AC-U13 already made for the parts of a topic page: a part that hides itself reads as a
feature that does not exist. All three are always served.

**What it replaced.** The two hand-written cards on home: "Daily Action Set" and the "3-Minute Memory Sprint"
badged *RAPID RECALL*, whose copy promised "topics approaching their forgetting curve threshold". The short
door now goes to the same memory-boost page, but says how many questions are due and how long they take, or
that none are. Door text lives in `reasons.yaml` (bumped to `planner_reasons_v3`), not in the component.

**Tests.** 7 unit tests on the rule, 2 integration tests on the endpoint (all three doors always present,
today's minutes matching the set, the long door matching the topic page, every door closing with a reason once
the set is finished). 856 pass; `tsc` and `next build` clean.

**Not verified in a browser**, for the same reason as F1: the states worth seeing need real answers submitted
as her, which writes to her record.

**One thing I left alone:** `ruff check app` fails on a pre-existing 123-character line in
`learn/lessons.py:527`, from another session's uncommitted work. My own files pass; I did not touch it, but it
blocks a clean lint of the tree.

---

## 12. Status — 25 Oct 2026: F3 built

`POST /learn/homework-photo` and `/student/homework`: she photographs the worksheet she has been set, and Scholr
offers the topic it is on — her lesson, the bank questions on it, the Tutor scoped there.

**It cannot do her homework.** The reader (`homework_read/v1`, role `homework_reader`, Flash-Lite live — the
Batch API carries no inline images) transcribes the questions and is told to leave out any working already on
the page. The reply schema has **no field an answer could arrive in**, and extra keys are dropped, so a model
that answers anyway has nowhere to put it (a unit test pins that). What she is handed is a topic page, which
starts with the help ladder like every other (PRINCIPLES §18, §27).

**The topic is decided by code.** The prompt forbids naming a subject, chapter or syllabus. The text is matched
against her own books by `knowledge.topics_for_text`: one embedding, compared with her subjects' chunks, each
chunk voting for the objectives it is tagged to, a topic scoring its nearest chunk so a long chapter cannot
out-vote a short section. It is held to **the bar lessons already hold** — HIGH or MEDIUM, by the subject's own
calibrated thresholds and the same `retrieval_state` rule — rather than a number I invented. Below it she is
told plainly to pick the topic herself, and an integration test sends a French Revolution worksheet to prove it.

**The retrieval boundary.** Working out which topic a page is on has to look across her subjects, so the
boundary is kept where it matters: only her enrolled subjects that Scholr explains are searched, and **no line
of any book comes back** — she is offered topic names, never an excerpt (PRINCIPLES §7). A test asserts the
matched page's own words appear nowhere in the response.

**Nothing is kept.** The photo is never written to disk (unlike answer photos), the text is in no table, and
**no retrieval log row is written** — a test counts them at zero. `llm_call` records cost and metadata only, as
it does for every call; it holds no prompt or reply text. `sniff_image` moved to `app/tools/images.py` so the
stored and unstored paths share one implementation, and the client's declared type is still never trusted.

**Refused before any model call:** a non-image (415), nothing (422), over 8 MB (413), and a guardian account
(403). Two tests assert `transport.requests == []` for those, so the refusal is proven to be free.

**Tests.** 5 unit, 5 integration. 866 pass; `tsc` and `next build` clean, with `/student/homework` in the route
list.

**Not verified in a browser, and no real photo has been through it.** Every test scripts the reader, so what is
proven is the plumbing, the guards and the matching — not how well Flash-Lite reads a phone photo of a
worksheet in a Dubai kitchen. That needs one real photo, which is the first thing to try when you next have the
app open; the match quality is the part most likely to need a second pass.

---

## 13. Status — 25 Oct 2026: run against her real record, and what it found

The app was started on the dev database (API on :8000, web on :3001, `AUTH_MODE=dev`) and the home page read.
Three things the tests could not have told us:

**F2's long door was broken, twice over.** It offered Maths 33.3 at "about 0 min" and gave the reason *"You've
finished today's set"* while **none** of her six questions was answered. Two faults, both now fixed and pinned
by a regression test:

- *It stopped at the first topic.* A topic page counts a part as done once she has answered any question in it,
  so 33.3's page had nothing left while the set still held its questions. The door now walks today's topics in
  the rule's order and takes the first with something on it (`sessions.deep_candidates`, at most three page
  reads), and when none has, it says so — not that she has finished.
- *The door was two hours long.* Looking past 33.3 landed on Sociology 1.1.1, whose page had **124 minutes**
  left. True, and useless for a door sized at 25. It now offers that topic's **next unfinished part** with that
  part's own minutes (`learn.next_part`): "about 10 min · starts with Check yourself, then Exam questions". The
  door's text says what it now does — carry on with one topic, a part at a time.

**B2's fix reads correctly, and one line of my own criticism was wrong.** The strip shows "Mon · IIT Foundation
— Biology · 16:30 / Sat · Mathematics · 15:30 / Thu · Physics/Chemistry · 16:30", from `GET /commitments`. So
the seeded record *does* hold an IIT Biology class, and §3 B2's claim that "Biology is not an IIT course at all"
was wrong — `docs/CONTEXT.md` lists three subjects, her record lists four. What was actually wrong in the
hard-coded strip was the times (19:00 against 16:30) and the fact that it was written into the page at all.

**F1 and F3 could not be seen.** The finish panel needs every question in the set answered, and the homework
page needs a real photo — both write to her record, so neither was exercised. `/student/homework` renders and
its copy reads as intended; what it does with a real worksheet is still unknown.

**Also noticed, not mine and not fixed:** every page load calls `GET /api/auth/streams`, which 404s under
`AUTH_MODE=dev` — the only failing request on the page. It belongs to the registration flow in the uncommitted
tree.

867 tests pass (one new regression test); `tsc` clean. `.claude/launch.json` was corrected: the web port was
3000 where `package.json` serves 3001, and the API now runs with `--reload`.

---

## 14. Status — 26 Oct 2026: the student home page, rebuilt (§5.1)

She said the page looked ordinary and unorganised. It was: nine decisions before any work, the same subjects
listed three times, and a dark "COMMAND STUDIO" banner over a strip of uppercase telemetry.

**It now answers the five questions PRINCIPLES §UX says home must answer, in that order**, and nothing else:

1. *What should I do today, and why?* One card, one primary button. `nextAction` picks it: the next item on her
   plan (with the planner's own reason), else what is left of today's set, else — when the day is done — what
   tomorrow starts with (F1). Beside it, the two things she is most likely to want unprompted: photograph her
   homework (F3) and ask the Tutor.
2. *How long have I got?* The three doors (F2), now equal height with the topic statement clamped — Sociology
   1.1.1's statement is a paragraph and was swamping its card.
3. *What am I struggling with?* "Worth your attention": her open mistakes and topics going quiet, each linking
   to its own topic page (`focus` carries `objective_id`; the web type had dropped it).
4. *What is today shaped like?* Today's plan, with the week's classes read from `GET /commitments` underneath it.
5. *How am I progressing?* "Your week" in four plain facts, "Topics secure" counted from answered questions, and
   recently secure topics when there are any.

**What went:** the gradient hero and its badges, the four-tile uppercase telemetry strip, the "Academic
Toolkits" code-badge grid, and two of the three places subjects were listed. **What the numbers say now:**
"3 of 7 days you studied", under a line that reads *"A rest day is a rest day. Nothing here is a streak to keep
up."* — the honest substitute for a streak this document argued for in §2.

**On a phone** (375px, checked) the order is the same and nothing scrolls sideways. Subjects moved out of the
left column to full width *below* the two-column grid: on a phone her week was otherwise behind nine subject
cards.

**The sidebar was renamed to match** — Today, Subjects, Today's set, My homework, Question bank, My notebooks,
Tutor, IIT classes, My progress, My mistakes, Mock exams, Past papers, Tests set for me, What my parents see —
in place of Command Center, Daily Action Set, Topic Question Bank, Performance Analytics, Error Log & Repair and
the "LIVE" and "BRIDGE" badges that meant nothing. Section headings in words, not shouted abbreviations.

**Two things to fix that are not the page's doing**, both visible on her record today:

- The planner returns two contradictory notices at once — *"Today is full, so optional practice was left out"*
  and *"No study time is planned for today. Enjoy the break!"* — on a Monday whose only block is the 16:30 IIT
  class. They sit together on the page and read as nonsense. The page shows what the API sends; the engine is
  what needs looking at.
- A mistake reads *"The student has not correctly calculated…"*. The marker writes about her in the third
  person, to her.

`tsc` and `next build` clean. Checked against her real record at 375px and at desktop width; no request on the
page fails except the pre-existing `GET /api/auth/streams` (§13).

---

## 15. Status — 26 Oct 2026: the contradictory plan notices, and what they were hiding

**The bug.** `build_plan` sets `overload = sum(core minutes) > capacity`, which is vacuously true when capacity
is zero, and `_out` appended the "overload" notice whenever that flag was set. The `lighter_day` notice was
already guarded with `capacity_minutes > 0`; `overload` never was. So a day with no study time in it said both
*"Today is full, so optional practice was left out"* and *"No study time is planned for today. Enjoy the
break!"*.

**The fix** is a pure rule, `engine.notice_codes`, so the decision is one readable function instead of three
`if`s in the output builder: a day with no capacity says only that, and the text still comes from
`reasons.yaml`. Covered by unit tests on the rule and an integration test that drives the real endpoint with
zero availability and core work waiting. Both were run against the old code first and fail on it, reproducing
her exact pair of notices.

**Also fixed: a flaky test of my own.** The long-door regression test from §13 assumed today's set contained
particular fixture questions. The set's tie-break is a hash of her id and the day, and the seeded id differs
per run, so it passed alone and failed in the full suite. It now answers every servable question on the topic
and asserts the invariant rather than the arrangement. 870 pass.

**What the bug was hiding, which matters more.** Her availability is 120 minutes on Monday and Thursday, and
each of those days carries a two-hour IIT class. Capacity is availability − commitments − buffer, so:

| | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Available | 120 | 120 | 120 | 120 | 90 | 150 | 60 |
| IIT class | 120 | — | — | 120 | — | 120 | — |
| **Scholr can plan** | **0** | 102 | 102 | **0** | 76 | ~25 | 51 |

**Two days a week Scholr plans nothing at all, and a third is nearly nothing** — and those are the days built
around her coaching classes, which is exactly when the IGCSE ground underneath them is worth ten minutes. The
app currently answers those evenings with "Enjoy the break!". The daily set still appears (it does not read
capacity), so the two halves of the home page disagree about whether there is anything to do.

This is her household data, not a code fault: the planner is doing what it was told.

**Answered the same day (D-E8): leave it.** Those evenings really are full — the 120 minutes is her whole study
budget for the day, and the class takes it. So Monday and Thursday are rest-from-Scholr days by design, and the
planner is right to say so.

That settled the planner and left one thing inconsistent: on a full evening the plan said "Enjoy the break!"
while the card above it pushed 26 minutes of questions.

**Answered the same day (D-E9): home leads with the quiet day.** With no capacity, the card now reads
*"Today is full. IIT Foundation — Biology at 16:30. Scholr has nothing scheduled today — that's the plan, not a
gap."* There is no primary button: today's set is a quiet line of text underneath (*"If you do want something:
today's set, 6 questions"*), because it is her own queue of mistakes and revision rather than something the day
has scheduled. Photographing homework and the Tutor stay, since both answer "something came up" rather than
"do more work". The three doors are unchanged below.

Two of her seven evenings now say one thing instead of two contradictory ones. Checked live on her record,
which is a Monday.

---

## 16. Note — 26 Oct 2026: I broke the dev server while checking this

Worth writing down so it is not repeated. `npx next build` and `next dev` share `apps/web/.next`, and running
the build against a running dev server replaced the chunks it was serving: every page came back as unstyled
markup with 404s for `layout.css` and `main-app.js`. The dev server was the user's own, started before this
session.

Recovering it meant stopping that process, clearing `.next` and starting the dev server again — and then
stopping an orphaned `next dev` child that survived its parent and held port 3001 while serving a directory
that no longer existed.

**The rule:** never run `next build` while a dev server is up in the same checkout. Stop it, build, clear
`.next`, start it again — which is what the verification at the end of §15 did.

---

## 17. Finding — 27 Oct 2026: OpenRouter withdrew Flash-Lite's batch variant

Running the Crucible job for the Sociology pre-mock failed at submit:
`Model 'google/gemini-2.5-flash-lite:batch' does not have a :batch endpoint` (HTTP 400). Nothing was generated
and nothing was spent.

**It used to work here.** `llm_call` holds 26 successful calls on that exact model id on 22 Sep 2026, and one
error today. OpenRouter's catalogue now lists batch variants for 71 models, and **no Gemini 2.5 model is among
them** — batch starts at Gemini 3.x. So the variant was withdrawn some time between 22 Sep and now, which is
not something a lesson in this repository could have predicted.

**What still batches:** `z-ai/glm-5.3-flash:batch` is listed, and it carries 173 successful calls from 21–22
Sep. So the two roles that matter most — `lesson_writer` and `exam_walker` — are unaffected.

| Role | live model | batch_model | state |
|---|---|---|---|
| lesson_writer | z-ai/glm-5.3-flash | `:batch` | listed, works |
| exam_walker | z-ai/glm-5.3-flash | `:batch` | listed, works |
| crucible_writer | google/gemini-2.5-flash-lite | `:batch` | **gone** |
| lesson_illustrator | google/gemini-2.5-flash-lite | `:batch` | **gone** |
| examiner_report_extractor | google/gemini-2.5-flash-lite | `:batch` | **gone** |
| summarizer | google/gemini-2.5-flash-lite | `:batch` | **gone** |

(GLM's batch endpoint is evidenced by the catalogue and by September's successful calls, not by a submit made
today. A submit test would cost about a tenth of a cent if certainty is wanted before the next lessons run.)

**What was done about it.** `batching.run` gained `live=True`: the same requests, one at a time, on the role's
live model — same prompt, same schema, same guards, same person-approval gate. It is chosen by a person
(`--live`, as `app.jobs.lessons` has had since September), never by the module, so "it never falls back"
remains true. `app.jobs.crucible` now exposes `--live`, and the pre-mock debates were run that way.

**Decision D-E10.** Those four roles still name a `batch_model` that does not exist, so every one of their jobs
fails until someone passes `--live`. Either drop the `batch_model` line from the four (they then run live on the
same model, at the live price — these jobs cost cents, so the difference is cents), or leave the config as a
record of intent and always pass the flag. Moving them to a Gemini 3.x batch model would break the two-model
rule of 21 Sep, which is the user's to change, not mine. STUDENT-APP §17's table needs the same correction.

---

## 18. Fix — 27 Oct 2026: Crime questions were tagged to Research Methods and Identity

Found while reviewing the pre-mock debates: the Crucible on **1.1.1 (the positivist approach)** had written about
the causes of crime. It had done exactly what it should — taken the highest-mark essay the bank holds for that
topic — and the bank held *"To what extent can a lack of status in society explain criminal behaviour?"*
(`0495/22/MJ23/Q3(e)`) under a Research Methods objective.

**The pattern.** 0495 papers map question numbers to syllabus units, and the bank agrees with that overwhelmingly:

| Section | Unit | Correct tags | Stray tags (before) |
|---|---|---|---|
| Paper 1 Q1 | 1 Research methods | 317 | 4 |
| Paper 1 Q2 | 2 Identity | 246 | 44 |
| Paper 1 Q3 | 3 Inequality | 184 | 13 |
| Paper 2 Q1 | 4 Family | 210 | 22 |
| Paper 2 Q2 | 5 Education | 189 | 33 |
| Paper 2 Q3 | 6 Crime | 219 | **67** |

The extractor (an LLM) assigns objective codes, and it cross-tags across units. This is the same failure that
produced commit `d6bb572` — old Media questions tagged onto Research Methods and Identity — whose fix,
`without_off_syllabus_tags`, blanks the codes of questions a manifest marks as off-syllabus. That guard cannot
help here, because these questions *are* on the syllabus; they are simply in the wrong unit.

**What was fixed.** The 14 Paper 2 Q3 questions carrying 1.x or 2.x tags had those tags removed; their 6.x Crime
tags are untouched, so nothing is lost for Crime revision. Research Methods went from 59 servable questions to
49, Identity from 47 to 43. Paper 2 Q3 now has zero strays. The 1.1.1 debate was redone and is now built on
*"To what extent is positivism the best approach to sociological research?"* (Paper 1 Q1) — it shares that essay
with 1.2.1, which is reasonable for two topics about sociological approaches.

One judgement call worth a second opinion: `0495/21/MJ25/Q3(a)(i)` is *"Define the term: peer group"*, a 2-mark
definition that was tagged to Identity. It is a perfectly good Identity definition, but it was set in the Crime
section, so the rule took it. Putting it back is a one-line change if you disagree.

**Not fixed, and still there: 116 stray tags in the other five sections**, including 44 from Paper 1 Q2 (Identity
questions tagged to Crime and Inequality) and 33 from Paper 2 Q2. They do not touch the pre-mock scope, which is
why they were left. **Decision D-E11:** the deterministic guard this wants is paper-section → unit, applied at
import the way `without_off_syllabus_tags` is, with the mapping declared in each paper's manifest rather than
inferred. That would stop the next import re-creating all of it.

**How it was fixed matters too:** by SQL against her database, not through a service, so there is no audit row
for it. The affected rows were backed up first. A re-import would undo it until the guard exists.

---

## 19. Fix — 27 Oct 2026: tagging guarded by paper section (D-E11)

**The guard.** A paper's structure is printed on the paper, so the manifest now states it:
`question_units: {"1": "4", "2": "5", "3": "6"}` on each 0495 question paper (Paper 1 → Research methods,
Identity, Inequality; Paper 2 → Family, Education, Crime). `without_cross_unit_tags` drops any objective code
the extractor puts outside a question's own unit, beside `without_off_syllabus_tags` in the import. A question
number the manifest does not mention is left alone, and a paper that declares nothing is untouched, so the other
subjects are unaffected. Unit-tested.

**The mapping was checked, not assumed.** Across every component and series in the bank, the dominant unit per
question number is the same: P1 Q1→1, Q2→2, Q3→3; P2 Q1→4, Q2→5, Q3→6 — 1,365 tags agreeing against 183
strays. That includes the 2023 and 2024 papers, whose older format kept Crime at Paper 2 Q3 with Media at Q4
(which is what `untagged_questions: ["4"]` already handled).

**The cleanup, and where it deliberately stopped.** 14 more questions lost 83 stray tags. Strays fell from 183
to 33:

| Section | Correct | Strays before | After |
|---|---|---|---|
| P1 Q1 Research methods | 317 | 4 | 4 |
| P1 Q2 Identity | 246 | 44 | 12 |
| P1 Q3 Inequality | 184 | 13 | 0 |
| P2 Q1 Family | 210 | 22 | 9 |
| P2 Q2 Education | 189 | 33 | 8 |
| P2 Q3 Crime | 219 | 67 | 0 |

The 33 that remain are **seven questions whose only tags are strays**. Applying the rule would leave them with
no objective at all, which takes them out of practice entirely rather than putting them in the right place, so
they were left for a person:

| Question | Marks | Should be | Tagged |
|---|---|---|---|
| `0495/11/MJ23/Q2(e)` To what extent does a global culture exist? | 15 | 2 Identity | 3 Inequality |
| `0495/11/MJ25/Q2(e)` Discuss how courts are an effective agency of formal social control | 8 | 2 Identity | 6 Crime |
| `0495/12/MJ23/Q1(f)` Explain why feminists believe society is based on conflict | 10 | 1 Research methods | 3 Inequality |
| `0495/12/MJ25/Q2(a)(i)` Define the term: penal system | 2 | 2 Identity | 6 Crime |
| `0495/22/MJ23/Q2(a)` What is meant by 'social factors'? | 2 | 5 Education | 3 Inequality |
| `0495/22/MJ25/Q1(c)` Describe three ways socialisation in the family can differ for girls and boys | 6 | 4 Family | 2 Identity |
| `0495/22/MJ25/Q2(a)(i)` Define the term: value consensus | 2 | 5 Education | 1 Research methods |

Most of these are the Identity/Crime overlap: **2.2 "How does society control us?" covers formal social control
— police, courts, the penal system — and so does unit 6**. The extractor is not being stupid; the boundary is
genuinely thin. The right answer for each is a topic within its own unit, which is a judgement about content,
not something a section rule can make. **D-E12.**

**Effect on the pre-mock scope:** Research Methods 59 → 49 servable questions, Identity 47 → 37, Family and
Education unchanged at 33 and 32. Every one of those is now a question from the section it belongs to.

---

## 20. Fix — 28 Oct 2026: six of the seven retagged (D-E12)

Each went to a topic inside its own unit, chosen against the objective statements and, where one existed, the
way comparable questions are already tagged:

| Question | Now | Why |
|---|---|---|
| `0495/11/MJ23/Q2(e)` To what extent does a global culture exist? | 2.3 | 2.3.3 is "Globalisation and its impact on social identity" |
| `0495/11/MJ25/Q2(e)` Discuss how courts are an effective agency of formal social control | 2.2 | 2.2.3 is "Agencies of formal social control: police, courts" |
| `0495/12/MJ25/Q2(a)(i)` Define the term: penal system | 2.2 | same objective |
| `0495/22/MJ23/Q2(a)` What is meant by 'social factors'? | 5.3 | the bank's other "factors" Education questions ("in-school factors", "home factors") are both 5.3 |
| `0495/22/MJ25/Q1(c)` Describe three ways socialisation in the family can differ for girls and boys | 4.2 | 4.2.1 primary socialisation, 4.2.3 feminist views of gender roles |
| `0495/22/MJ25/Q2(a)(i)` Define the term: value consensus | 5.2 | 5.2.1 is the functionalist view |

**The seventh was left, and the instruction was to retag all of them, so here is the reasoning.**
`0495/12/MJ23/Q1(f)` is *"Explain why feminists believe that society is based on conflict."* Its section is
Paper 1 Q1, which the section rule maps to unit 1, Research methods. But unit 1 has one topic, 1.1 "How do
sociologists approach the study of society?", whose objectives are positivism, interpretivism, mixed methods
and the evaluation of research choices. Feminist conflict theory is none of those.

The reason is the syllabus change: MJ23 is an **old-format** paper whose Paper 1 Section A was *"theory and
methods"*, so a theory question belonged there. In the 2025–27 syllabus the theory half moved, and consensus
versus conflict is now **2.2.2**, in Identity. So its true home is outside the unit its section implies.

Forcing it onto 1.1 would put feminist conflict theory under "the positivist approach" — the same kind of
wrong tag this whole exercise removed, just within a unit instead of across one.

**Answered the same day (D-E13): moved to 2.2**, where consensus and conflict now sits — content over section.
Because that contradicts the section rule, a re-import would have stripped it straight back out, so the
exception is declared rather than remembered: a manifest may now name a question **in full** and give it its own
unit, and `0495-mj23-qp12` carries `"1(f)": "2"` with the reason beside it. The full ref wins over the question
number in `without_cross_unit_tags`; unit-tested. The bank now has **zero** cross-unit tags.

**The pre-mock bank, final:** Research Methods 48, Identity 39, Family 34, Education 34 servable questions —
every one from the section it belongs to.

---

## 21. One paragraph, if you read nothing else

The learning engine is good and honest, and almost everything needed to make the app habit-forming is already
inside it, one feature away from her. The twelve in §4 need no new model, no new service and, bar one photo
call, no new spend: a day that finishes (F1), a door sized to ten minutes (F2), her own homework as the daily
trigger (F3), one tap on what class covered (F4), and a ledger that tells her what an hour is worth (F5).
What stops them working today is smaller than they are: no reminder exists, Sociology gives her nothing back
until a parent intervenes, and the home page asks nine decisions before she learns anything. None of it needs
points, badges or streaks — and the reason to come back has to be that yesterday was worth it.
