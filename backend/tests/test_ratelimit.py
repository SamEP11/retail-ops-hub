"""Límite de intentos de login con Redis."""

import redis

from app.core.config import get_settings
from app.core.ratelimit import LoginLimiter, get_login_limiter
from app.main import app
from app.models import AuditLog
from tests.conftest import PASSWORD

LOGIN = "/api/v1/auth/login"


def attempt(client, email, password="clave-equivocada"):
    return client.post(LOGIN, data={"username": email, "password": password})


def test_bloquea_tras_cinco_fallos(client, make_user, db):
    user = make_user()
    for _ in range(get_settings().login_max_attempts):
        assert attempt(client, user.email).status_code == 401

    # Ni siquiera con la clave correcta: la cuenta está en enfriamiento
    r = attempt(client, user.email, PASSWORD)
    assert r.status_code == 429
    assert 0 < int(r.headers["Retry-After"]) <= get_settings().login_window_seconds
    assert db.query(AuditLog).filter_by(action="auth.login_blocked").count() == 1


def test_login_exitoso_reinicia_el_contador(client, make_user):
    user = make_user()
    for _ in range(get_settings().login_max_attempts - 1):
        attempt(client, user.email)
    assert attempt(client, user.email, PASSWORD).status_code == 200
    assert attempt(client, user.email).status_code == 401  # vuelve a contar desde cero


def test_el_bloqueo_es_por_cuenta(client, make_user):
    victim, other = make_user(), make_user()
    for _ in range(get_settings().login_max_attempts):
        attempt(client, victim.email)
    assert attempt(client, other.email, PASSWORD).status_code == 200


def test_si_redis_se_cae_el_login_sigue_funcionando(client, make_user):
    broken = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1)
    app.dependency_overrides[get_login_limiter] = lambda: LoginLimiter(broken)
    try:
        user = make_user()
        assert attempt(client, user.email, PASSWORD).status_code == 200
    finally:
        app.dependency_overrides.clear()
