# ADR 0003 — Modelo del catálogo e importación masiva

**Estado:** aceptada · **Fecha:** 2026-11-01

## Contexto

Una marca de moda vende el mismo estilo en varias tallas y colores, a dos tipos de cliente
(público B2C y mayoristas B2B) con precios distintos. El equipo comercial mantiene el
catálogo en Excel y necesita cargarlo sin errores ni duplicados.

## Decisión

1. **Producto = estilo, Variante = SKU.** El producto ("Camisa Oxford") guarda lo común
   (nombre, marca, categoría, estado); la variante guarda talla, color, código de barras y
   es lo que se vende y se cuenta en bodega. Restricción única `(product_id, size, color)`.
2. **Precios en tabla aparte** `prices(price_list_id, variant_id, amount)` y listas de precio
   (`B2C`, `B2B`) como datos, no columnas. Agregar una lista "Outlet" no requiere migración.
3. **Dinero como `Decimal` / `NUMERIC(14,2)`**, nunca `float`: 0.1 + 0.2 ≠ 0.3 en float.
   Se normaliza a 2 decimales al entrar a la API.
4. **Estados del producto:** `draft` (en preparación), `active` (a la venta), `archived`
   (fuera de catálogo, sin borrar historial). No se puede activar sin variantes activas.
5. **Códigos normalizados** (SKU, estilo, cupón): sin espacios y en mayúsculas, para que
   `cam-01 ` y `CAM-01` sean el mismo.
6. **Importación todo o nada:** se valida el archivo completo (formato, duplicados en el
   archivo, conflictos con la base) y si hay un solo error no se guarda nada; se devuelven
   todos los errores con fila y columna.
7. **`dry_run=true` por defecto**: el flujo es previsualizar y luego confirmar. Una carga de
   5.000 filas mal hecha es muy difícil de deshacer.
8. **Upsert idempotente** por `style_code` y `sku`: importar dos veces el mismo archivo no
   cambia nada.

## Consecuencias

- Consultar el precio requiere un join; mitigado con índices y subconsultas en el listado.
- La importación corre en la misma petición HTTP (máx. 5.000 filas, ~2 s). Para archivos
  más grandes se moverá a una tarea en segundo plano con Redis (worker, Sprint 5).
