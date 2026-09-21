# Principles — v2.1

These rules are authoritative. If code, a plan, or another document conflicts with them, stop and raise it.

## 1. Purpose

Build a system that progressively understands how the student learns, identifies what she needs next, teaches effectively, **measures whether she actually learned it**, remembers what happened, adapts, and helps her become **increasingly independent**.

This is a Student Intelligence Platform, not a chatbot and not a collection of agents.

## 2. Philosophy

- Product for one, architecture for many.
- Student-first, AI-second.
- Learning progress over conversation volume. Mastery over marks.
- AI increases independence, not dependency.
- Path-level orchestration, subject-level intelligence.
- Isolate retrieval, integrate learning.
- Agents for reasoning; deterministic code for deterministic work.
- Shared knowledge where concepts overlap; separate curriculum context where objectives differ.
- Evidence over AI confidence.
- Career guidance explores possibilities, not destiny.
- Child safety and parental oversight are architectural requirements.

## 3. Priority order

```
Learning correctness > Student safety > Data integrity > Personalization
  > Maintainability > Observability > Performance > Visual polish
```

When in conflict, choose:

| Instead of | Choose |
|---|---|
| Impressive AI behaviour | Reliable educational behaviour |
| More agents | Simpler architecture |
| Answering immediately | Helping the student learn independently |
| AI confidence | Evidence |
| Short-term engagement | Long-term learning |
| Measuring ourselves | Independent measurement |

## 4. Mandatory rules

**Architecture**
1. Do not build an agent per subject or per function.
2. A component is agentic only if it needs multi-step reasoning, tool use, stateful next-action selection, or conversational adaptation. An LLM call alone is not an agent. Prefer explicit state machines with narrow LLM steps.
3. Deterministic services for deterministic work: arithmetic, algebra, units, scoring, mastery, scheduling, dates, routing on known context.
4. Subject-level intelligence comes from configuration, not duplicated code.
5. `learning_event` is the append-only source of truth. Mastery, mistakes and memory are projections that can be rebuilt.
6. Modular monolith. No microservices without a demonstrated need.

**Knowledge and grounding**
7. Retrieval boundaries are strict: current objective → current subject → related subject (via concept graph) → general reference. No uncontrolled cross-domain retrieval.
8. Never silently fall back from grounded retrieval to ungrounded LLM knowledge. General knowledge is always labelled as such.
9. Never invent sources, studies, sociologists, statistics, dates or syllabus content. If it is not in retrieved material, omit it or label it and advise verification.
10. Student notes are useful for personalization but are **low authority for correctness** (they may contain misconceptions).
11. Publicly accessible ≠ free to reproduce. Every source records owner, licence, version. Copyrighted material stays private and is never redistributed.

**Assessment and evidence**
12. Never show a generated question whose answer cannot be verified — deterministically for maths/science, against source material and format rules for essay subjects.
13. Every evaluation carries a confidence. Low-confidence evaluations go to review and **do not change mastery**.
14. Mastery reflects evidence, independence and retention — not marks alone.
15. Confidence (the student's) is tracked separately from mastery.
16. Success is measured with independent evidence (held-out past-paper forms, school results), not only the system's own estimates.
17. Validate learning outcomes before expanding the platform.

**Pedagogy**
18. Ask for an attempt before helping; escalate help gradually; never refuse help more than once.
19. After a full solution is revealed, the student must succeed on a similar item before progress is credited.
20. Assistance decreases as competence increases.
21. The planner optimizes workload, not task count. Core academic work and rest are protected; optional tasks go first.
22. Every major feature must contribute to the learning loop: Understand → Plan → Teach → Practice → Evaluate → Remember → Adapt → Guide → Improve.

**Safety, privacy, integrity**
23. Safety is policy-driven, deterministic where possible, auditable and testable. An LLM never decides escalation policy.
24. High-severity safety responses are pre-written and reviewed, not generated.
25. The AI never claims to be human, encourages secrecy, fosters emotional dependency, or replaces parents, teachers or counsellors.
26. The student is told plainly what parents can see. Oversight protects; it does not surveil.
27. **Academic integrity:** never write, rewrite or substantially produce work that will be submitted for Cambridge or school assessment (e.g. Global Perspectives coursework). Coach the process instead.
28. Collect only the personal data a feature needs.

**Engineering**
29. No mock intelligence in production paths: no fake scores, mastery, retrieval, recommendations or analytics.
30. Do not build features because they look impressive in a demo.

## 5. North Star

**Learning Progress per Hour**, anchored to independent assessment:

```
LPH = (normalized gain on held-out assessments, app-supported topics
       − normalized gain, comparison topics)
      ÷ student hours in the app on those topics
```

Tracked alongside: retention ratio, recurrence of diagnosed mistakes, share of items solved without help, school results. The formula may evolve after baseline data exists; changes are recorded in PHASE-1.md.

Not success metrics: conversations, messages, tokens, agents, questions generated, screen time, streaks.

## 6. Career guidance

Current interest in Civil Services / IAS is respected and never treated as destiny. Language is exploratory ("areas worth exploring"), never predictive ("you should become X"). Career identity evolves with evidence.

## 7. UX

Calm, focused, encouraging, age-appropriate, uncluttered. No agent-centric UI, no AI jargon, minimal gamification, streaks never at the expense of healthy learning. The student should feel "this understands how I learn", not "I'm talking to 20 bots".

The home screen answers: What should I do today? Why does it matter? How am I progressing? What am I struggling with? What next?
