"""Pruebas de integración del login y del token JWT."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.models import AuditLog
from app.permissions import Role
from tests.conftest import PASSWORD


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "up"}
    assert "X-Request-ID" in r.headers


def test_login_correcto_devuelve_token(client, make_user):
    user = make_user(Role.BODEGA)
    r = client.post("/api/v1/auth/login", data={"username": user.email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_minutes * 60


def test_login_ignora_mayusculas_en_email(client, make_user):
    user = make_user(Role.BODEGA)
    r = client.post(
        "/api/v1/auth/login", data={"username": user.email.upper(), "password": PASSWORD}
    )
    assert r.status_code == 200


def test_login_clave_incorrecta_y_usuario_inexistente_dan_el_mismo_error(client, make_user):
    user = make_user()
    wrong = client.post("/api/v1/auth/login", data={"username": user.email, "password": "x" * 12})
    missing = client.post("/api/v1/auth/login", data={"username": "nadie@x.dev", "password": "x"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()  # no revelamos qué emails existen


def test_usuario_inactivo_no_puede_entrar(client, make_user):
    user = make_user(active=False)
    r = client.post("/api/v1/auth/login", data={"username": user.email, "password": PASSWORD})
    assert r.status_code == 401


def test_login_queda_auditado(client, make_user, db):
    user = make_user()
    client.post("/api/v1/auth/login", data={"username": user.email, "password": PASSWORD})
    client.post("/api/v1/auth/login", data={"username": user.email, "password": "mala-clave-1"})
    actions = [a.action for a in db.query(AuditLog).order_by(AuditLog.id)]
    assert actions[-2:] == ["auth.login", "auth.login_failed"]


def test_me_devuelve_usuario_y_permisos(client, make_user, login):
    user = make_user(Role.ANALISTA)
    r = client.get("/api/v1/auth/me", headers=login(user))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == user.email
    assert "reports:read" in body["permissions"]
    assert "users:manage" not in body["permissions"]


def test_sin_token_da_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_token_expirado_da_401(client, make_user):
    user = make_user()
    s = get_settings()
    expired = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_token_firmado_con_otra_clave_da_401(client, make_user):
    user = make_user()
    forged = jwt.encode(
        {"sub": str(user.id)}, "otra-clave-cualquiera-de-32-bytes-o-mas", algorithm="HS256"
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_usuario_desactivado_pierde_acceso_con_token_vigente(client, make_user, login, db):
    user = make_user()
    headers = login(user)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
