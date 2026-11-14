"""FastAPI application factory.

Run (from apps/api): uv run uvicorn app.main:create_app --factory --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

import app.models_registry  # noqa: F401
from app.core.config import Settings, get_settings
from app.core.db import get_session_factory
from app.core.errors import install_error_handlers
from app.core.telemetry import install_request_id
from app.llm.gateway import LLMGateway
from app.modules.assessment.api import router as assessment_router
from app.modules.classlog.api import router as classlog_router
from app.modules.critic.api import router as critic_router
from app.modules.curriculum.api import router as curriculum_router
from app.modules.enrollment.api import router as enrollment_router
from app.modules.evaluation.api import router as evaluation_router
from app.modules.external_training.api import router as external_training_router
from app.modules.goals.api import router as goals_router
from app.modules.identity.api import router as identity_router
from app.modules.knowledge.api import router as knowledge_router
from app.modules.learn.api import router as learn_router
from app.modules.mastery.api import router as mastery_router
from app.modules.memory.api import router as memory_router
from app.modules.mistakes.api import router as mistakes_router
from app.modules.planner.api import router as planner_router
from app.modules.progress.api import router as progress_router
from app.modules.readiness.api import router as readiness_router
from app.modules.routing.api import router as routing_router
from app.modules.safety.api import router as safety_router
from app.modules.studies.api import router as studies_router
from app.modules.tutoring.api import router as tutoring_router


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    gateway: LLMGateway | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    dev_docs = settings.app_env != "prod"
    app = FastAPI(
        title="Scholr API",
        version="0.1.0",
        docs_url="/docs" if dev_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev_docs else None,
    )
    app.state.settings = settings
    app.state.session_factory = session_factory or get_session_factory()
    app.state.gateway = gateway  # built on first use when None (see app.core.deps.llm_gateway)

    install_request_id(app)
    install_error_handlers(app)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for router in (
        identity_router,
        curriculum_router,
        assessment_router,
        evaluation_router,
        mastery_router,
        mistakes_router,
        knowledge_router,
        safety_router,
        tutoring_router,
        enrollment_router,
        classlog_router,
        planner_router,
        progress_router,
        studies_router,
        memory_router,
        routing_router,
        external_training_router,
        readiness_router,
        critic_router,
        goals_router,
        learn_router,
    ):
        app.include_router(router)
    return app
