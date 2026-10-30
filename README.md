# Retail Ops Hub

Backoffice para una marca de moda que vende en Shopify (B2C y mayoristas B2B):
catálogo maestro, inventario por bodega, clientes, usuarios con permisos y KPIs.

**Estado:** Sprint 1 — fundaciones (API, base de datos, migraciones, login, roles, auditoría, CI).

## Arrancar en un comando

Requisitos: Docker Desktop y Git.

```bash
cp .env.example .env          # en PowerShell: copy .env.example .env
docker compose up --build
```

- API y documentación interactiva: http://localhost:8000/docs
- Salud: http://localhost:8000/health

Crear usuarios demo (uno por rol, contraseña `Demo12345!`, **solo local**):

```bash
docker compose exec api python -m app.cli seed
```

| Email | Rol |
| --- | --- |
| admin@retailops.dev | admin |
| comercial@retailops.dev | comercial |
| bodega@retailops.dev | bodega |
| analista@retailops.dev | analista |

En `/docs` pulsa **Authorize**, entra con uno de ellos y prueba los endpoints:
verás que `bodega` recibe 403 en `/api/v1/users`.

## Tests, lint y tipos

```bash
docker compose exec api pytest
docker compose exec api ruff check .
docker compose exec api mypy app
```

Los tests corren contra PostgreSQL real (base `retail_ops_test`) y la crean con
las migraciones, así que también prueban que las migraciones funcionan.

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
    core/           configuración, seguridad, logs
    permissions.py  roles y permisos
  alembic/          migraciones
  tests/            unitarias e integración
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

## API (Sprint 1)

| Método | Ruta | Permiso |
| --- | --- | --- |
| GET | `/health` | público |
| POST | `/api/v1/auth/login` | público |
| GET | `/api/v1/auth/me` | autenticado |
| GET | `/api/v1/users` | `users:read` |
| POST | `/api/v1/users` | `users:manage` |
| GET | `/api/v1/users/{id}` | `users:read` |
| PATCH | `/api/v1/users/{id}` | `users:manage` |
| GET | `/api/v1/audit` | `audit:read` |
