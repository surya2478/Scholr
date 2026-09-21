# Scholr — Personal AI Learning OS

A personal learning system for one Cambridge IGCSE student (Year 10, Dubai).
**Product for one, architecture for many. Student-first, AI-second.**

## Read before working

1. `docs/PRINCIPLES.md` — non-negotiable rules. Wins every conflict.
2. `docs/CONTEXT.md` — the student, subjects, exams, materials, open unknowns.
3. `docs/ARCHITECTURE.md` — modules, data model, pipelines, API.
4. `docs/PHASE-1.md` — current scope, weekly plan, acceptance criteria.
5. `docs/PHASE-2.md` — Complete IGCSE; Sociology exam readiness first. Opened 16 Sep 2026.
6. `docs/PHASE-3.md` — IIT Foundation integration, opened 16 Sep 2026 at the user's request.
7. `docs/STUDENT-APP.md` — streams, subject → chapter → topic navigation and topic pages; approved 19 Sep 2026.

`docs/RUNNING-AT-HOME.md` — how the app runs on the home machine, the first admin account and her phone.

`docs/ROADMAP.md` describes later phases. **Do not build ahead of the current phase.**

## Current phase

Phase 1 — thin vertical slice: **IGCSE Mathematics 0580 (Extended)** first, then **IGCSE Sociology 0495**.
Anything not listed in `docs/PHASE-1.md` needs explicit approval from the user.

Phase 3 (IIT Foundation integration) runs alongside it, opened at the user's request ahead of Phase 2, and is
scoped by `docs/PHASE-3.md`. Its rule is **complement, never duplicate**: Scholr records the external classes
and reinforces the IGCSE ground beneath them. It never teaches the IIT syllabus.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind, KaTeX (render), MathLive (maths input), PWA |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, `uv` |
| Database | PostgreSQL 16 + pgvector + full-text search, row-level security |
| Jobs | Postgres-backed scheduler (no Redis/Celery in Phase 1) |
| LLM | OpenRouter behind internal `LLMGateway` (role-based model config) |
| Deterministic tools | SymPy (maths), Pint (units, from Physics slice) |
| Tests | pytest, testcontainers (Postgres), Playwright (critical UI flows), `evals/` |

## Layout

```
apps/web/                 Next.js student + parent UI
apps/api/app/core/        config, db, auth, rbac, telemetry, errors
apps/api/app/modules/     one folder per domain module (see ARCHITECTURE §3)
apps/api/app/llm/         gateway, prompts/ (versioned files), schemas
apps/api/app/tools/       deterministic tools (math, units, scoring, dates)
apps/api/subject_configs/ YAML subject expertise configs (Pydantic-validated)
content/curriculum/         curriculum + concept-map seeds — committed
apps/api/tests/
evals/                    benchmark datasets + runners
content/manifests/        source manifests (licence, owner, version) — committed
content/private/          raw source files — GITIGNORED, never committed
infra/                    docker-compose, deployment
docs/
```

## Conventions

- **Modular monolith.** Modules talk through their `service.py` public functions. Never import another module's `repository.py` or ORM models.
- Module files: `api.py` (routes only), `service.py` (business logic), `repository.py` (DB), `models.py` (ORM), `schemas.py` (Pydantic), `tests/`.
- No business logic in API routes or React components.
- **All LLM calls go through `app/llm/gateway.py`** with a named role and a versioned prompt file in `app/llm/prompts/`. No inline prompt strings.
- LLM output that drives logic must be validated against a Pydantic schema → one retry → typed failure. Never regex-parse free text.
- Arithmetic, algebra, units, scoring, dates, mastery → deterministic code. Never trust an LLM for these.
- **`learning_event` is append-only.** Mastery, mistakes, and learning memory are projections derived from events. Features emit events; they do not write projections directly.
- **Subject behaviour lives in `subject_configs/*.yaml`.** No `if subject == "maths"` in engine code — add a config field instead.
- A subject config declares a **`stage`**, and that is the only switch engine code may branch on: `taught` (full engine), `lessons` (a retrieval corpus and grounded topic lessons; no questions, marking or Tutor yet — added 19 Sep 2026 for Physics), `planned` (syllabus known; no questions, corpus or marking yet — may be named as revision, never set or marked) or `external` (learnt elsewhere; only recorded). A `taught` subject carries retrieval, pedagogy and evaluation blocks; a `lessons` subject carries retrieval and pedagogy only; for the others they are absent, not invented. You cannot teach to a syllabus nobody has verified.
- Every table with student data carries `student_id` (and `tenant_id`) and has an RLS policy.
- **No mock intelligence.** Fixtures only in `tests/fixtures/` and `evals/`, clearly named.
- Never commit copyrighted source material. Never show long verbatim textbook passages to the user.
- Changing a prompt, model assignment, rubric, or subject config ⇒ run the evals for the affected subject and report results.
- Audit-log: auth events, permission changes, ingestion, assessment creation, evaluation overrides, safety actions.
- Application logs must not contain conversation text or answers. Those live only in their tables.

## Commands

Dev environment: Windows 11. Run from `apps/api` unless noted. `uv` is invoked as `python -m uv`.

```
docker compose -f infra/docker-compose.yml up -d          # (repo root) Postgres 16 + pgvector on :5433
docker compose -f infra/docker-compose.home.yml --env-file infra/home.env up -d --build   # (repo root) the whole app on the home machine — see docs/RUNNING-AT-HOME.md
python -m uv sync                                          # install dependencies
python -m uv run alembic upgrade head                      # migrate dev DB (owner role)
python -m uv run python -m app.seed.curriculum ../../content/curriculum/igcse-maths-0580.yaml ../../content/curriculum/igcse-sociology-0495.yaml
python -m uv run python -m app.seed.curriculum ../../content/curriculum/iit-maths-grade9.yaml ../../content/curriculum/iit-physics-grade9.yaml ../../content/curriculum/iit-chemistry-grade9.yaml ../../content/curriculum/iit-biology-grade9.yaml   # external IIT Foundation courses (Phase 3)
python -m uv run python -m app.seed.curriculum ../../content/curriculum/igcse-physics-0625.yaml ../../content/curriculum/igcse-chemistry-0620.yaml ../../content/curriculum/igcse-biology-0610.yaml   # planned subjects: syllabus known, nothing taught yet
python -m uv run python -m app.seed.concepts ../../content/curriculum/concepts-*.yaml   # concept maps: four IIT<->IGCSE pairs plus the cross-subject one
python -m uv run python -m app.seed.household ../../content/private/seed/household.yaml
python -m uv run python -m app.jobs.ingest register        # register manifest sources, extract text-layer PDFs
python -m uv run python -m app.jobs.ingest ocr --source <key> [--pages 1-50]   # vision OCR (resumable)
python -m uv run python -m app.jobs.ingest status
python -m uv run python -m app.jobs.ingest repair --source <key>   # deterministic repair of stored OCR pages (JSON-escape damage)
python -m uv run python -m app.jobs.ocr_eval --source <key> [--prompt P --output markdown --dpi 220 --bands 1 --model M] [--pages 13,15]   # screen OCR settings vs stored pages (defaults = manifest)
python -m uv run uvicorn app.main:create_app --factory --reload --port 8000   # API; OpenAPI docs at /docs (dev)
python -m uv run python -m app.jobs.dev_token <auth_subject>   # dev bearer token for a seeded user (AUTH_MODE=dev)
python -m uv run python -m app.jobs.accounts create-admin --email you@example.com --name "You"   # first admin (AUTH_MODE=local); asks for the password at the prompt
python -m uv run python -m app.jobs.accounts pending|approve <email> [--role student --streams IGCSE,IIT]|reject <email>   # decide who may use the app (docs/STUDENT-APP.md D7)
python -m uv run python -m app.jobs.question_bank [--only <qp-key>] [--role <extractor-role>] [--dry-run]   # past papers -> question bank; --dry-run compares with the bank, saves nothing
python -m uv run python -m app.jobs.question_bank --recheck --dry-run [--only <qp-key>]   # report recheck results without changing rows
python -m uv run python -m app.jobs.mark_scheme_parse [--only <ms-key>] [--bank] [--dump]   # parse mark-scheme tables (no LLM); compare with bank
python -m uv run python -m app.jobs.marking_eval --subject igcse-maths [--role maths_marker] [--scripts 40] [--run]   # AC-E4 synthetic benchmark (no DB writes); without --run prints the estimate only
python -m uv run python -m app.jobs.knowledge chunk|embed [--source KEY]   # build retrieval chunks (no LLM) / embed pending chunks
python -m uv run python -m app.jobs.knowledge search "query" --subject igcse-maths [--objective 32.2]   # try retrieval + state
python -m uv run python -m app.jobs.memory pending|summarize [--limit 20]   # learning memory from ended sessions (Flash-Lite; idle sessions make no call)
python -m uv run python -m app.jobs.retrieval_eval [--run]   # AC-K2 recall@8 + state agreement; without --run prints the estimate only
python -m uv run python -m app.jobs.tutor_eval [--run]       # AC-K3/K4 tutor checks (Flash-Lite); without --run prints the estimate only
python -m uv run python -m app.jobs.ao_tag --subject igcse-sociology [--write]   # tag the bank with assessment objectives from the subject config (no LLM)
python -m uv run python -m app.jobs.examiner_insights [--subject igcse-maths] [--only <er-key>] [--run] [--force]   # examiner reports -> attributed per-question points (AC-R6); without --run prints the estimate only
python -m uv run python -m app.jobs.lessons --subject igcse-maths [--limit N] [--stale] [--run] [--recheck]   # topic lessons (docs/STUDENT-APP.md); without --run prints the estimate only; --recheck applies a stricter guard with no calls
python -m uv run python -m app.jobs.illustrate --subject igcse-maths [--limit N] [--redo] [--run]   # offer diagrams for written lessons (AC-U14); without --run prints the estimate only
python -m uv run python -m app.jobs.illustrate --subject igcse-maths --review | --approve <codes> | --reject <codes>   # a person decides what she sees
python -m uv run python -m app.jobs.walkthroughs --subject igcse-maths [--only 15.4,1.6] [--redo] [--run]   # a real past-paper question solved per topic (AC-U16); without --run prints the estimate only
python -m uv run python -m app.jobs.walkthroughs --subject igcse-maths --review | --approve <codes> | --reject <codes>   # a person decides what she sees
python -m uv run python -m app.jobs.lessons --subject igcse-maths --pilot 1.1,15.4 --prompt-version v4 [--model M] --run   # write beside the stored lessons for comparison; saves nothing (output in evals/runs/)
python -m uv run python -m app.jobs.templates generate --subject igcse-maths [--per-template 5] [--dry-run]   # SymPy-verified template items (no LLM)
python -m uv run python -m app.jobs.notify once|loop [--every 30]   # deliver guardian safety notifications (run `loop` beside the API)
bash ../../infra/scripts/backup_restore_rehearsal.sh      # AC-O2 backup + restore rehearsal inside the Docker container
python -m uv run pytest tests -q                           # unit + integration (integration needs Docker DB)
npm --prefix ../web install && npm --prefix ../web run dev   # web app on :3000 (proxies /api to :8000); sign in with a dev_token
python -m uv run ruff format app tests migrations && python -m uv run ruff check app tests migrations
```

Database roles: the API connects as `scholr_app` (no superuser, no BYPASSRLS — RLS applies). Migrations use the owner role via `MIGRATION_DATABASE_URL`. Tests use `scholr_test` with the same split.

## Definition of done (per feature, where applicable)

API + business logic + persistence + events emitted + AI behaviour behind gateway + error handling for every failure mode in ARCHITECTURE §20 + audit/telemetry + unit/integration tests + evals passing + UI. "The UI works" is not done.

## Don't

- Add agents, frameworks (LangGraph, Redis, Celery, vector DBs), or services not in ARCHITECTURE.md without approval.
- Silently fall back from grounded retrieval to ungrounded LLM knowledge.
- Serve a generated maths question whose answer SymPy has not verified.
- Update mastery from an evaluation below the confidence threshold.
- Build Phase 2+ features, visual polish, or gamification ahead of the learning loop.
- Hard-code student data outside seed files.
