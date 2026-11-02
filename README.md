# Retail Ops Hub

Backoffice para una marca de moda que vende en Shopify (B2C y mayoristas B2B):
catálogo maestro, inventario por bodega, clientes, usuarios con permisos y KPIs.

**Estado:** Sprint 2 — catálogo (productos, variantes, precios B2C/B2B, cupones, importación desde Excel) y panel web.

| Sprint | Entregó |
| --- | --- |
| 1 | API, base de datos, migraciones, login JWT, roles, auditoría, CI |
| 2 | Catálogo, importación masiva, cupones, rate limiting del login, panel React |

## Arrancar en un comando

Requisitos: Docker Desktop y Git.

```bash
cp .env.example .env          # en PowerShell: copy .env.example .env
docker compose up --build
```

- **Panel web:** http://localhost:5173 (la primera vez tarda ~1 min instalando dependencias)
- API y documentación interactiva: http://localhost:8000/docs
- Salud: http://localhost:8000/health

Crear usuarios demo (uno por rol, contraseña `Demo12345!`, **solo local**) y un catálogo de
10 productos con 48 variantes:

```bash
docker compose exec api python -m app.cli seed
```

| Email | Rol |
| --- | --- |
| admin@retailops.dev | admin |
| comercial@retailops.dev | comercial |
| bodega@retailops.dev | bodega |
| analista@retailops.dev | analista |

Entra al panel con `comercial@retailops.dev` para ver el catálogo e importar archivos
(hay una plantilla descargable). Con `bodega@retailops.dev` verás el catálogo pero no el
botón de importar. En `/docs` puedes probar cada endpoint con **Authorize**.

Tras 5 intentos fallidos de login con el mismo email, la cuenta queda bloqueada 15 minutos
(respuesta 429). Para desbloquear en local: `docker compose exec redis redis-cli FLUSHDB`.

## Tests, lint y tipos

```bash
# backend
docker compose exec api pytest
docker compose exec api ruff check .
docker compose exec api mypy app
# frontend
docker compose exec web npm test
docker compose exec web npm run lint
docker compose exec web npm run typecheck
```

Los tests del backend corren contra PostgreSQL y Redis reales (base `retail_ops_test`,
Redis base 15) y crean la base con las migraciones, así que también las prueban. Los del
frontend simulan la API con `fetch` falso y prueban lo que ve el usuario.

### Sin Docker (opcional)

Necesitas Python 3.12+ y un Postgres local con las bases `retail_ops` y `retail_ops_test`.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Migraciones

```bash
# después de cambiar un modelo en app/models/
docker compose exec api alembic revision --autogenerate -m "describe el cambio"
# REVISA el archivo generado antes de aplicarlo
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1   # probar que se puede revertir
```

Nunca cambies la base a mano: todo cambio de esquema es una migración versionada.

## Estructura

```
backend/
  app/
    api/routes/     endpoints HTTP (delgados: validan, llaman servicios, responden)
    api/deps.py     sesión de BD, usuario actual, require(permiso)
    services/       reglas de negocio (aquí vive la lógica, no en los endpoints)
    models/         tablas (SQLAlchemy)
    schemas/        contratos de entrada y salida (Pydantic)
    core/           configuración, seguridad, errores, logs, rate limiting
    permissions.py  roles y permisos
  alembic/          migraciones
  tests/            unitarias e integración
frontend/
  src/api/          cliente HTTP, tipos de la API y endpoints
  src/auth/         sesión (token, usuario actual, permisos)
  src/pages/        pantallas: login, productos, detalle, importación
  src/components/   layout y piezas reutilizables
  Dockerfile        build de producción servido por nginx
docs/adr/           decisiones de arquitectura
docs/sprints/       planeación y retro de cada sprint
.github/            CI, plantilla de PR, plantillas de issues
```

## Flujo de trabajo

1. Cada tarea es un issue (historia o defecto) en GitHub Projects.
2. Rama `feature/<issue>-descripcion` o `fix/<issue>-descripcion` desde `main`.
3. Commits convencionales: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
4. PR con la plantilla; la CI (lint, tipos, migraciones, tests, build Docker) debe pasar.
5. Squash merge a `main`.

## API

| Método | Ruta | Permiso |
| --- | --- | --- |
| GET | `/health` | público |
| POST | `/api/v1/auth/login` | público (máx. 5 fallos / 15 min) |
| GET | `/api/v1/auth/me` | autenticado |
| GET, POST | `/api/v1/users` | `users:read`, `users:manage` |
| GET, PATCH | `/api/v1/users/{id}` | `users:read`, `users:manage` |
| GET | `/api/v1/audit` | `audit:read` |
| GET, POST | `/api/v1/categories` | `catalog:read`, `catalog:write` |
| GET, POST | `/api/v1/products` | `catalog:read`, `catalog:write` |
| GET, PATCH | `/api/v1/products/{id}` | `catalog:read`, `catalog:write` |
| POST | `/api/v1/products/{id}/variants` | `catalog:write` |
| PATCH | `/api/v1/variants/{id}` | `catalog:write` |
| GET | `/api/v1/price-lists` | `catalog:read` |
| PUT | `/api/v1/price-lists/{code}/prices` | `catalog:write` |
| GET, POST | `/api/v1/coupons` | `catalog:read`, `catalog:write` |
| PATCH | `/api/v1/coupons/{id}` | `catalog:write` |
| POST | `/api/v1/coupons/check` | `catalog:read` |
| POST | `/api/v1/catalog/import?dry_run=true` | `catalog:write` |
| GET | `/api/v1/catalog/import/template` | `catalog:write` |
