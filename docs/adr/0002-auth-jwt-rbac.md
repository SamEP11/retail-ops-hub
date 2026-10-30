# ADR 0002 — Autenticación JWT y control de acceso por permisos

**Estado:** aceptada · **Fecha:** 2026-10-30

## Contexto

Cuatro perfiles (admin, comercial, bodega, analista) con accesos distintos. El panel web y
el servicio de sincronización consumen la misma API.

## Decisión

1. **JWT de acceso** (HS256, 30 min) enviado como `Authorization: Bearer`. Sin refresh token
   en el sprint 1; se agrega cuando exista el frontend.
2. **Contraseñas con Argon2id** (`pwdlib`).
3. **Los endpoints piden permisos, no roles** (`require(Permission.USERS_MANAGE)`). El mapeo
   rol → permisos vive en `app/permissions.py`. Agregar un rol no obliga a tocar endpoints.
4. **El rol se lee de la BD en cada request**, no del token: desactivar o degradar a alguien
   tiene efecto inmediato aunque su token siga vigente.
5. **Auditoría en la misma transacción** que el cambio: si el cambio falla, no queda log falso;
   si el log falla, no queda cambio sin rastro.
6. **Login con respuesta idéntica** para email inexistente y contraseña errada, y verificación
   de hash en ambos casos, para no revelar qué correos existen.
7. Debe existir **al menos un admin activo** (regla de negocio en `services/users.py`).

## Consecuencias

- Una consulta extra por request para leer al usuario; aceptable a esta escala, cacheable en Redis.
- Los permisos en código no se editan desde la UI; si el negocio lo pide, se mueven a tablas.
