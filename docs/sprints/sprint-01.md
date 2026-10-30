# Sprint 1 — Fundaciones

**Objetivo:** un backend desplegable con login, roles, auditoría y pipeline en verde.

## Historias

| # | Historia | Estado |
| --- | --- | --- |
| 1 | Como dev, quiero levantar todo con `docker compose up` para empezar en minutos | Hecho |
| 2 | Como admin, quiero iniciar sesión y ver mis permisos | Hecho |
| 3 | Como admin, quiero crear, listar y editar usuarios con un rol | Hecho |
| 4 | Como admin, quiero ver quién cambió qué y cuándo | Hecho |
| 5 | Como equipo, queremos CI que bloquee PRs con errores | Hecho |

### Criterios de aceptación destacados

- **Dado** un usuario de bodega, **cuando** pide la lista de usuarios, **entonces** recibe 403.
- **Dado** un admin que degrada a otro admin, **cuando** el degradado usa su token vigente,
  **entonces** pierde el acceso de inmediato.
- **Dado** un único admin activo, **cuando** intenta quitarse el rol o desactivarse,
  **entonces** recibe 409 y nada cambia.
- **Dado** un email inexistente o una clave errada, **cuando** se intenta el login,
  **entonces** ambos casos responden igual (401) y quedan auditados.

## Métricas de calidad al cierre

- 39 tests automáticos (unitarios + integración contra Postgres), 0 fallando.
- ruff y mypy (modo estricto) sin errores.
- `alembic check`: migraciones sincronizadas con los modelos.

## Retro

- **Bien:** permisos separados de roles desde el inicio; tests contra BD real.
- **Mejorar:** falta refresh token y rate limiting del login (ataques de fuerza bruta).
- **Acción:** rate limiting con Redis entra al backlog del sprint 2.

## Siguiente: Sprint 2 — Catálogo

Productos, variantes talla/color, listas de precio B2C/B2B, cupones, importación desde Excel
y el panel React + TypeScript.
