"""Pruebas de integración de gestión de usuarios, permisos y auditoría."""

import pytest

from app.models import AuditLog
from app.permissions import Role

NEW_USER = {
    "email": "nuevo@retailops.dev",
    "full_name": "Nuevo Usuario",
    "password": "Clave-Segura-456",
    "role": "bodega",
}


def test_admin_crea_usuario_y_queda_auditado(client, make_user, login, db):
    admin = make_user(Role.ADMIN)
    r = client.post("/api/v1/users", json=NEW_USER, headers=login(admin))
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == NEW_USER["email"]
    assert "password" not in body and "hashed_password" not in body

    log = db.query(AuditLog).filter_by(action="user.create", actor_id=admin.id).one()
    assert log.entity_id == str(body["id"])
    assert log.changes == {"email": NEW_USER["email"], "role": "bodega"}


@pytest.mark.parametrize("role", [Role.COMERCIAL, Role.BODEGA, Role.ANALISTA])
def test_roles_no_admin_no_pueden_crear_usuarios(client, make_user, login, role):
    user = make_user(role)
    r = client.post("/api/v1/users", json=NEW_USER, headers=login(user))
    assert r.status_code == 403
    assert r.json()["detail"] == "Falta el permiso users:manage"


def test_email_duplicado_da_409(client, make_user, login):
    admin = make_user()
    headers = login(admin)
    client.post("/api/v1/users", json=NEW_USER, headers=headers)
    dup = {**NEW_USER, "email": NEW_USER["email"].upper()}
    assert client.post("/api/v1/users", json=dup, headers=headers).status_code == 409


@pytest.mark.parametrize(
    "field, value",
    [("email", "no-es-email"), ("password", "corta"), ("role", "superadmin"), ("full_name", "")],
)
def test_validacion_de_entrada_da_422(client, make_user, login, field, value):
    admin = make_user()
    r = client.post("/api/v1/users", json={**NEW_USER, field: value}, headers=login(admin))
    assert r.status_code == 422


def test_listado_paginado_y_filtrado(client, make_user, login):
    admin = make_user()
    for _ in range(3):
        make_user(Role.BODEGA)
    make_user(Role.ANALISTA)
    headers = login(admin)

    page = client.get("/api/v1/users", params={"limit": 2}, headers=headers).json()
    assert page["total"] == 5 and len(page["items"]) == 2

    bodega = client.get("/api/v1/users", params={"role": "bodega"}, headers=headers).json()
    assert bodega["total"] == 3
    assert all(u["role"] == "bodega" for u in bodega["items"])


def test_cambio_de_rol_aplica_de_inmediato(client, make_user, login):
    admin = make_user(Role.ADMIN)
    other = make_user(Role.ADMIN)
    other_headers = login(other)
    assert client.get("/api/v1/users", headers=other_headers).status_code == 200

    r = client.patch(f"/api/v1/users/{other.id}", json={"role": "bodega"}, headers=login(admin))
    assert r.status_code == 200
    # Mismo token de antes: el rol se lee de la BD, no del token.
    assert client.get("/api/v1/users", headers=other_headers).status_code == 403


def test_patch_audita_solo_lo_que_cambio(client, make_user, login, db):
    admin = make_user()
    target = make_user(Role.BODEGA)
    client.patch(
        f"/api/v1/users/{target.id}",
        json={"role": "comercial", "full_name": target.full_name},
        headers=login(admin),
    )
    log = db.query(AuditLog).filter_by(action="user.update").one()
    assert log.changes == {"role": {"from": "bodega", "to": "comercial"}}


def test_no_se_puede_quitar_el_ultimo_admin(client, make_user, login):
    admin = make_user(Role.ADMIN)
    headers = login(admin)
    for body in ({"role": "analista"}, {"is_active": False}):
        r = client.patch(f"/api/v1/users/{admin.id}", json=body, headers=headers)
        assert r.status_code == 409
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "admin"


def test_con_otro_admin_si_se_puede_degradar(client, make_user, login):
    admin = make_user(Role.ADMIN)
    make_user(Role.ADMIN)
    r = client.patch(f"/api/v1/users/{admin.id}", json={"role": "analista"}, headers=login(admin))
    assert r.status_code == 200


def test_usuario_inexistente_da_404(client, make_user, login):
    headers = login(make_user())
    assert client.get("/api/v1/users/9999", headers=headers).status_code == 404
    assert client.patch("/api/v1/users/9999", json={}, headers=headers).status_code == 404


def test_auditoria_solo_para_admin(client, make_user, login):
    admin, analista = make_user(Role.ADMIN), make_user(Role.ANALISTA)
    assert client.get("/api/v1/audit", headers=login(analista)).status_code == 403
    r = client.get("/api/v1/audit", params={"action": "auth.login"}, headers=login(admin))
    assert r.status_code == 200
    assert r.json()["total"] == 2  # los dos logins de arriba
