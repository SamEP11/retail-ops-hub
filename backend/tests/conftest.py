"""Fixtures compartidas.

Los tests corren contra un PostgreSQL real (no SQLite): así probamos JSONB, enums
y constraints iguales a producción. La BD de test se crea con las migraciones de
Alembic, de modo que también probamos que las migraciones funcionan.
"""

import os
from collections.abc import Callable, Iterator

# Debe ir ANTES de importar la app: la configuración se lee al importar.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/retail_ops_test",
)
os.environ["ENVIRONMENT"] = "test"
# Base 15 de Redis solo para tests: se limpia entre tests sin tocar datos de desarrollo.
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["JWT_SECRET"] = "secreto-solo-para-tests-1234567890"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core.ratelimit import get_redis  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.permissions import Role  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services import users  # noqa: E402

PASSWORD = "Clave-Segura-123"
ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


@pytest.fixture(scope="session", autouse=True)
def _migrated_db() -> Iterator[None]:
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(ALEMBIC_INI), "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """Cada test arranca con tablas vacías: los tests no dependen del orden."""
    get_redis().flushdb()
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE audit_logs, users, prices, variants, products, categories, coupons "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    counter = iter(range(1, 1000))

    def _make(role: Role = Role.ADMIN, email: str | None = None, active: bool = True) -> User:
        n = next(counter)
        user = users.create(
            db,
            UserCreate(
                email=email or f"{role.value}{n}@test.dev",
                full_name=f"Usuario {n}",
                password=PASSWORD,
                role=role,
            ),
            actor_id=None,
            ip=None,
        )
        if not active:
            user.is_active = False
            db.commit()
        return user

    return _make


@pytest.fixture
def as_role(make_user: Callable[..., User], login: Callable[[User], dict[str, str]]):
    """Headers de un usuario nuevo con el rol pedido: `as_role(Role.BODEGA)`."""

    def _as(role: Role) -> dict[str, str]:
        return login(make_user(role))

    return _as


@pytest.fixture
def login(client: TestClient) -> Callable[[User], dict[str, str]]:
    def _login(user: User) -> dict[str, str]:
        r = client.post("/api/v1/auth/login", data={"username": user.email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login
