from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

import app.models_registry  # noqa: F401
from app.core.auth import issue_dev_token
from app.core.config import API_ROOT, get_settings
from app.core.db import Base, set_rls_context
from app.main import create_app
from app.seed.curriculum import load_file, seed_curriculum
from app.seed.household import HouseholdIn, seed_household

MATHS_CURRICULUM = API_ROOT.parents[1] / "content" / "curriculum" / "igcse-maths-0580.yaml"

# Fixture household (test data only).
TEST_HOUSEHOLD = {
    "tenant": {"name": "Test family"},
    "student": {"display_name": "Test Student", "auth_subject": "test|student", "year_group": "Year 10"},
    "guardians": [
        {"display_name": "Test Parent", "auth_subject": "test|parent"},
        {"display_name": "Other Parent", "auth_subject": "test|other-parent"},
    ],
    "enrollments": [{"subject": "igcse-maths", "tier": "extended", "exam_session": "2028-06"}],
}


def _reachable(eng: Engine) -> bool:
    try:
        eng.connect().close()
    except Exception:  # noqa: BLE001
        return False
    return True


@pytest.fixture(scope="session")
def owner_engine() -> Iterator[Engine]:
    """Owner role: runs migrations and cleanup. Never used for assertions about access."""
    url = get_settings().test_migration_database_url
    if not url:
        pytest.skip("TEST_MIGRATION_DATABASE_URL not set")
    eng = create_engine(url, future=True)
    if not _reachable(eng):
        pytest.skip("test database not reachable (docker compose -f infra/docker-compose.yml up -d)")
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def engine(owner_engine: Engine) -> Iterator[Engine]:
    """Application runtime role (no superuser, no BYPASSRLS) — same as production."""
    url = get_settings().test_database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = create_engine(url, future=True)
    if not _reachable(eng):
        pytest.skip("application role cannot connect to the test database")
    yield eng
    eng.dispose()


@pytest.fixture
def clean_db(owner_engine: Engine) -> Iterator[None]:
    yield
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with owner_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture
def household_world(engine: Engine, clean_db: None) -> SimpleNamespace:
    """Maths curriculum + TEST_HOUSEHOLD, seeded through the application role."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    maths = load_file(MATHS_CURRICULUM)
    with factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_curriculum(s, maths)
        ids = seed_household(s, HouseholdIn.model_validate(TEST_HOUSEHOLD))
    return SimpleNamespace(factory=factory, maths=maths, **ids)


@pytest.fixture
def api_client(household_world: SimpleNamespace) -> Iterator[TestClient]:
    with TestClient(create_app(session_factory=household_world.factory)) as client:
        yield client


@pytest.fixture
def auth_headers() -> Callable[..., dict[str, str]]:
    def make(subject: str, *, mfa: bool = True) -> dict[str, str]:
        return {"Authorization": f"Bearer {issue_dev_token(subject, get_settings(), mfa=mfa)}"}

    return make
