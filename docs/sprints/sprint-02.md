# Sprint 2 — Catálogo

**Objetivo:** que el equipo comercial pueda cargar y consultar el catálogo completo
(productos, variantes, precios B2C/B2B y cupones) desde un panel web.

## Historias

| # | Historia | Estado |
| --- | --- | --- |
| 6 | Como comercial, quiero crear productos con variantes talla/color y sus precios | Hecho |
| 7 | Como comercial, quiero importar el catálogo desde Excel y ver los errores por fila antes de guardar | Hecho |
| 8 | Como comercial, quiero actualizar precios de una lista en bloque por SKU | Hecho |
| 9 | Como comercial, quiero crear cupones con vigencia, canal, mínimo de compra y usos | Hecho |
| 10 | Como usuario, quiero buscar productos por nombre, estilo, marca o SKU y filtrarlos | Hecho |
| 11 | Como admin, quiero que el login se bloquee tras varios intentos fallidos | Hecho |
| 12 | Como usuario, quiero un panel web para ver y gestionar el catálogo | Hecho |

### Criterios de aceptación destacados

- **Dado** un archivo con un solo error, **cuando** se importa, **entonces** no se guarda
  nada y se listan todos los errores con fila y columna.
- **Dado** el mismo archivo importado dos veces, **entonces** la segunda vez no cambia nada.
- **Dado** un CSV exportado por Excel en español (con `;` y BOM), **entonces** se lee bien.
- **Dado** un cupón del 20 % con mínimo de $200.000, **cuando** la compra es de $100.000,
  **entonces** se rechaza con el motivo.
- **Dado** 5 intentos fallidos para un email, **cuando** llega el sexto, **entonces** 429
  aunque la contraseña sea correcta.
- **Dado** un usuario de bodega, **cuando** abre el panel, **entonces** ve productos pero no
  el botón de importar, y la API le responde 403 si lo intenta.

## Métricas de calidad al cierre

- Backend: 91 tests (unitarios + integración con Postgres y Redis reales).
- Frontend: 13 tests (Vitest + Testing Library) y un recorrido E2E manual con Playwright.
- ruff, mypy estricto, eslint y tsc sin errores; `alembic check` limpio.
- CI con 3 jobs: backend, frontend y build de las dos imágenes Docker.

## Retro

- **Bien:** el manejador global de errores de dominio eliminó los `try/except` de los
  endpoints; el seed reutiliza la importación y así la prueba cada vez.
- **Mejorar:** la migración autogenerada creaba un enum dos veces; hay que revisar siempre
  lo que genera Alembic. Tailwind 4 cambió cómo se declaran clases propias (`@utility`).
- **Acción:** agregar tests E2E automáticos con Playwright a la CI (Sprint 6).

## Siguiente: Sprint 3 — Inventario

Bodegas, movimientos (entradas, salidas, traslados, ajustes), kardex y reservas de stock
con bloqueo de filas para que dos pedidos simultáneos no vendan la misma unidad.
