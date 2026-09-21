# Roadmap after Phase 1 — v2.1

Each phase starts only after the previous gate. Requirements carried from the v2.0 master prompt are kept here so they are not lost; they are refined into a PHASE-N.md when that phase begins.

## Next slice — Physics 0625 and Chemistry 0620 (Jan 2027)

- Reuse `structured_math` pipeline; add Pint units tool, sign-convention and significant-figure checks.
- Physics evaluation criteria: concept, formula selection, substitution, units, calculation, physical interpretation.
- Chemistry: equation balancing tool (deterministic), mole calculations, periodic trends, terminology.
- Link IGCSE objectives to shared `concept` rows ready for IIT (Phase 3).

## Phase 2 — Complete IGCSE (Jan–Apr 2027)

**Sociology exam readiness first (exam May/Jun 2027):**
- Full 0495 syllabus coverage (remaining topics from syllabus).
- Timed past-paper workflow, command-word drills, essay planning, examiner-report insights.
- Exam readiness view by AO and topic by March 2027.

**Remaining subjects:** English, Biology, Global Perspectives, Arabic (syllabus codes U7).
- Subject configs + rubrics: English (content, structure, grammar, vocabulary, evidence, argument, style); Global Perspectives (research, source quality, evidence, perspectives, argument, bias, synthesis); Arabic (vocabulary, grammar, comprehension, writing, accuracy) with multilingual retrieval.
- **Global Perspectives coursework: integrity mode** — coach process only; never draft assessable work.
- Study Critic (rule-based patterns over events: inconsistency, cramming, unrealistic plans, rising help dependency, subject imbalance).
- Limited supportive responses for study frustration inside tutoring.
- Guardian dashboard v2: progress, consistency, strengths & gaps, assessments, goals, monthly review. Patterns, not surveillance.
- Cross-subject relationships via concept graph (e.g. Physics ↔ Maths graphs).

## Phase 3 — IIT Foundation integration

**Opened 16 Sep 2026 at the user's request, ahead of Phase 2. Scope and acceptance criteria: `docs/PHASE-3.md`.**

- `external_training_log`: topic, date, duration, score, weakness, questions attempted, questions missed.
- Trace: external IIT weakness → prerequisite concepts → IGCSE foundation weakness → targeted reinforcement.
- IIT subject configs (Maths, Physics, Chemistry) sharing concepts with IGCSE but separate depth, question style, mastery.
- Complement, never duplicate, the 6 h/week external training.

## Phase 4 — India Explorer (~30 min/day)

- Domains: History, Geography, Polity, Economics, GK/Current Affairs, Reading & Reasoning.
- Weekly rhythm: Mon History · Tue Geography · Wed Polity · Thu Economics · Fri Current Affairs · Sat GK challenge · Sun weekly review.
- Formats: stories, maps, timelines, quizzes, "why does this matter?", cross-subject links (IGCSE Geography, English reading comprehension).
- **Political neutrality policy** and a vetted, dated source list for polity and current affairs.
- Foundation exposure — not UPSC coaching.

## Phase 5 — Career intelligence

- Career Guide (agentic): explore careers, compare disciplines, skills, pathways, subject→career links. Options include engineering, CS, AI/data, economics, research, sciences, public policy, international relations, entrepreneurship, civil services.
- Career Radar: scheduled synthesis every 6–12 months over strengths, interests, projects, extracurriculars, achievements, learning patterns.
- Tables: `achievement`, `extracurricular_activity`, `project`, `career_interest`, `career_radar_report`, `journey_edge`.
- Language always exploratory. IAS is one possibility, not a destination.
- Supportive Companion (full): motivation, reflection, goal setting — never replaces parents/teachers/counsellors, never encourages secrecy or dependency, never claims to be human.

## Phase 6 — Advanced personalization

Spaced repetition and forgetting-curve retention (replacing mastery v1 retention thresholds), adaptive difficulty, exam readiness across all subjects, workload optimization, automatic gap detection, dependency trend modelling, learning-path optimization.

## Phase 7 — Platformization (only after real-world validation)

- Legal review: UAE PDPL, India DPDP Act 2023 (verifiable parental consent; restrictions on tracking/behavioural monitoring of children), exam-board content terms.
- Scoped guardian grants (parents see only assigned modules), teacher roles and dashboards, school/tenant onboarding.
- Additional curricula, countries, languages.
- Re-evaluate infrastructure (queues, caching, services) based on measured load.
