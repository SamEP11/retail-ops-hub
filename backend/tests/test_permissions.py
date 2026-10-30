"""Pruebas unitarias: lógica pura, sin BD ni HTTP. Son las más rápidas."""

import pytest

from app.permissions import ROLE_PERMISSIONS, Permission, Role, has_permission


def test_admin_tiene_todos_los_permisos():
    assert ROLE_PERMISSIONS[Role.ADMIN] == frozenset(Permission)


def test_todo_rol_tiene_permisos_definidos():
    assert set(ROLE_PERMISSIONS) == set(Role)


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        (Role.BODEGA, Permission.INVENTORY_WRITE, True),
        (Role.BODEGA, Permission.CATALOG_WRITE, False),
        (Role.COMERCIAL, Permission.CATALOG_WRITE, True),
        (Role.COMERCIAL, Permission.USERS_MANAGE, False),
        (Role.ANALISTA, Permission.REPORTS_READ, True),
        (Role.ANALISTA, Permission.INVENTORY_WRITE, False),
    ],
)
def test_matriz_de_permisos(role, permission, expected):
    assert has_permission(role, permission) is expected


def test_solo_admin_gestiona_usuarios_y_ve_auditoria():
    for role in Role:
        es_admin = role is Role.ADMIN
        assert has_permission(role, Permission.USERS_MANAGE) is es_admin
        assert has_permission(role, Permission.AUDIT_READ) is es_admin
