# ADR 0001 — Stack del backend

**Estado:** aceptada · **Fecha:** 2026-10-30

## Contexto

Backoffice transaccional (catálogo, stock, pedidos) con un equipo pequeño que domina Python.
Las ofertas objetivo piden además SQL, NoSQL, pruebas, Git y Docker.

## Decisión

- **FastAPI** (Python 3.12): validación con Pydantic, OpenAPI automático en `/docs`.
- **PostgreSQL 16** para lo transaccional: el stock exige transacciones y bloqueo de filas.
- **SQLAlchemy 2 (síncrono) + Alembic**: ORM con tipos y migraciones versionadas.
  Síncrono porque es más simple de razonar y depurar; FastAPI corre los endpoints `def`
  en un pool de hilos. Se revisa si un perfil de carga lo justifica.
- **MongoDB** (sprint 4) solo para payloads crudos de webhooks y eventos, de forma variable.
- **Redis** para colas de tareas y rate limiting.
- **Docker Compose** para el entorno local; **GitHub Actions** para CI.

## Consecuencias

- Los tests usan Postgres real, no SQLite: más lentos, pero detectan errores de producción
  (JSONB, enums, constraints).
- Dos motores de BD suman operación; se justifica porque cada uno guarda datos de forma distinta.
