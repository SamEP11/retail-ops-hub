"""Roles y permisos (RBAC).

Los permisos son acciones concretas; los roles son paquetes de permisos.
Los endpoints piden PERMISOS, nunca roles: así agregar un rol nuevo no obliga
a tocar los endpoints. Ver docs/adr/0002-auth-jwt-rbac.md.
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    COMERCIAL = "comercial"
    BODEGA = "bodega"
    ANALISTA = "analista"


class Permission(StrEnum):
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    CATALOG_READ = "catalog:read"
    CATALOG_WRITE = "catalog:write"
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    REPORTS_READ = "reports:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.COMERCIAL: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.INVENTORY_READ,
            Permission.CUSTOMERS_READ,
            Permission.CUSTOMERS_WRITE,
            Permission.REPORTS_READ,
        }
    ),
    Role.BODEGA: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.INVENTORY_READ,
            Permission.INVENTORY_WRITE,
        }
    ),
    Role.ANALISTA: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.INVENTORY_READ,
            Permission.CUSTOMERS_READ,
            Permission.REPORTS_READ,
        }
    ),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
