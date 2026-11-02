"""Importación masiva del catálogo desde CSV o Excel.

Una fila = una variante (SKU). Las filas con el mismo `style_code` forman un producto.

Reglas (ver docs/adr/0003-modelo-catalogo.md):
- Se valida TODO el archivo antes de escribir. Con un solo error, no se guarda nada y se
  devuelve la lista completa de errores con fila y columna, para corregir de una vez.
- `dry_run=True` hace todo el proceso dentro de una transacción y la revierte: sirve para
  previsualizar qué cambiaría.
- Es idempotente: importar dos veces el mismo archivo no duplica nada (upsert por
  style_code y por SKU).
- Columnas de precio dinámicas: `price_B2C`, `price_B2B`... una por lista existente.
"""

import csv
import io
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Price, PriceList, Product, ProductStatus, Variant
from app.schemas.catalog import ImportIssue, ImportReport
from app.services import audit

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024
REQUIRED = ("style_code", "product_name", "brand", "sku", "size", "color")
OPTIONAL = ("category", "description", "status", "barcode")
PRODUCT_FIELDS = ("product_name", "brand", "category", "description", "status")


class ImportFileError(Exception):
    """El archivo no se puede leer (formato, tamaño, encabezados)."""


@dataclass
class Row:
    number: int
    style_code: str
    product_name: str
    brand: str
    category: str
    description: str
    status: str
    sku: str
    size: str
    color: str
    barcode: str | None
    prices: dict[str, Decimal] = field(default_factory=dict)


# ---------- Lectura del archivo ----------


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excel guarda 7701234567890 como 7.70123456789e12
    return str(value).strip()


def _read_rows(filename: str, content: bytes) -> Iterator[list[str]]:
    if len(content) > MAX_BYTES:
        raise ImportFileError("El archivo supera 5 MB")
    name = filename.lower()
    if name.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise ImportFileError("No se pudo leer el Excel (.xlsx)") from exc
        sheet = wb.active
        if sheet is None:
            raise ImportFileError("El Excel no tiene hojas")
        for values in sheet.iter_rows(values_only=True):
            yield [_cell(v) for v in values]
    elif name.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")  # -sig quita el BOM que agrega Excel
        except UnicodeDecodeError as exc:
            raise ImportFileError("El CSV debe estar en UTF-8") from exc
        # Excel en español exporta CSV con ";"; detectamos el separador por el encabezado.
        first_line = text.splitlines()[0] if text else ""
        delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
        yield from csv.reader(io.StringIO(text), delimiter=delimiter)
    else:
        raise ImportFileError("Formato no soportado: usa .csv o .xlsx")


def parse(
    filename: str, content: bytes, price_list_codes: set[str]
) -> tuple[list[Row], list[ImportIssue]]:
    lines = _read_rows(filename, content)
    try:
        header = [h.strip().lower() for h in next(lines)]
    except StopIteration:
        raise ImportFileError("El archivo está vacío") from None

    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ImportFileError(f"Faltan columnas obligatorias: {', '.join(missing)}")
    price_cols = {h: h.removeprefix("price_").upper() for h in header if h.startswith("price_")}
    unknown_lists = sorted(set(price_cols.values()) - price_list_codes)
    if unknown_lists:
        raise ImportFileError(f"Listas de precio inexistentes: {', '.join(unknown_lists)}")

    rows: list[Row] = []
    errors: list[ImportIssue] = []
    for number, values in enumerate(lines, start=2):
        if not any(values):
            continue  # filas en blanco al final del Excel
        if len(rows) >= MAX_ROWS:
            raise ImportFileError(f"Máximo {MAX_ROWS} filas por archivo")
        data = dict(zip(header, values + [""] * (len(header) - len(values)), strict=False))

        def err(column: str | None, message: str, n: int = number) -> None:
            errors.append(ImportIssue(row=n, column=column, message=message))

        for col in REQUIRED:
            if not data.get(col):
                err(col, "Obligatorio")
        status = (data.get("status") or "draft").lower()
        if status not in {s.value for s in ProductStatus}:
            err("status", "Debe ser draft, active o archived")
        barcode = data.get("barcode") or None
        if barcode and not (barcode.isdigit() and 8 <= len(barcode) <= 14):
            err("barcode", "Debe tener entre 8 y 14 dígitos")

        prices: dict[str, Decimal] = {}
        for col, code in price_cols.items():
            raw = data.get(col, "").replace("$", "").replace(" ", "")
            if not raw:
                continue
            try:
                amount = Decimal(raw)
            except InvalidOperation:
                err(col, f"'{raw}' no es un número (usa punto decimal, sin separador de miles)")
                continue
            if amount < 0:
                err(col, "No puede ser negativo")
            prices[code] = amount.quantize(Decimal("0.01"))

        rows.append(
            Row(
                number=number,
                style_code=data["style_code"].upper(),
                product_name=data["product_name"],
                brand=data["brand"],
                category=(data.get("category") or "").lower(),
                description=data.get("description", ""),
                status=status,
                sku=data["sku"].upper(),
                size=data["size"],
                color=data["color"],
                barcode=barcode,
                prices=prices,
            )
        )
    return rows, errors


# ---------- Validación contra el propio archivo y la base ----------


def validate(db: Session, rows: list[Row]) -> list[ImportIssue]:
    errors: list[ImportIssue] = []

    def err(row: int, column: str | None, message: str) -> None:
        errors.append(ImportIssue(row=row, column=column, message=message))

    # 1. Duplicados dentro del archivo
    seen_sku: dict[str, int] = {}
    seen_barcode: dict[str, int] = {}
    seen_combo: dict[tuple[str, str, str], int] = {}
    first_of_style: dict[str, Row] = {}
    for r in rows:
        if r.sku in seen_sku:
            err(r.number, "sku", f"SKU repetido (ya está en la fila {seen_sku[r.sku]})")
        seen_sku.setdefault(r.sku, r.number)
        if r.barcode:
            if r.barcode in seen_barcode:
                err(r.number, "barcode", f"Repetido (fila {seen_barcode[r.barcode]})")
            seen_barcode.setdefault(r.barcode, r.number)
        combo = (r.style_code, r.size.lower(), r.color.lower())
        if combo in seen_combo:
            err(r.number, "size", f"Talla/color repetidos en el estilo (fila {seen_combo[combo]})")
        seen_combo.setdefault(combo, r.number)

        # Los datos del producto deben coincidir en todas las filas del mismo estilo
        first = first_of_style.setdefault(r.style_code, r)
        for f in PRODUCT_FIELDS:
            if getattr(r, f) != getattr(first, f):
                err(r.number, f, f"Distinto a la fila {first.number} del mismo style_code")

    # 2. Categorías existentes
    slugs = {r.category for r in rows if r.category}
    existing = set(db.scalars(select(Category.slug).where(Category.slug.in_(slugs))))
    for r in rows:
        if r.category and r.category not in existing:
            err(r.number, "category", f"La categoría '{r.category}' no existe")

    # 3. Conflictos con lo que ya está en la base
    db_by_sku = {
        v.sku: v
        for v in db.scalars(
            select(Variant).options(selectinload(Variant.product)).where(Variant.sku.in_(seen_sku))
        )
    }
    for r in rows:
        v = db_by_sku.get(r.sku)
        if v and v.product.style_code != r.style_code:
            err(r.number, "sku", f"El SKU ya pertenece al estilo {v.product.style_code}")

    if seen_barcode:
        owners = db.execute(
            select(Variant.barcode, Variant.sku).where(Variant.barcode.in_(seen_barcode))
        ).all()
        owner_by_barcode = dict(owners)
        for r in rows:
            owner = owner_by_barcode.get(r.barcode) if r.barcode else None
            if owner and owner != r.sku:
                err(r.number, "barcode", f"Ya lo usa el SKU {owner}")

    db_combos = db.execute(
        select(Product.style_code, Variant.size, Variant.color, Variant.sku)
        .join(Variant)
        .where(Product.style_code.in_(first_of_style))
    ).all()
    sku_by_combo = {(s, z.lower(), c.lower()): sku for s, z, c, sku in db_combos}
    for r in rows:
        owner = sku_by_combo.get((r.style_code, r.size.lower(), r.color.lower()))
        if owner and owner != r.sku:
            err(r.number, "size", f"Esa talla/color ya existe con el SKU {owner}")

    return sorted(errors, key=lambda e: (e.row, e.column or ""))


# ---------- Aplicación ----------


def apply(db: Session, rows: list[Row], lists: dict[str, PriceList], report: ImportReport) -> None:
    by_style: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_style[r.style_code].append(r)

    categories = {c.slug: c.id for c in db.scalars(select(Category))}
    products = {
        p.style_code: p
        for p in db.scalars(
            select(Product)
            .where(Product.style_code.in_(by_style))
            .options(selectinload(Product.variants).selectinload(Variant.prices))
        )
    }

    for style, style_rows in by_style.items():
        head = style_rows[0]
        attrs = {
            "name": head.product_name,
            "brand": head.brand,
            "description": head.description,
            "category_id": categories.get(head.category),
            "status": ProductStatus(head.status),
        }
        product = products.get(style)
        if product is None:
            product = Product(style_code=style, images=[], **attrs)
            db.add(product)
            report.products_created += 1
        elif any(getattr(product, k) != v for k, v in attrs.items()):
            for k, v in attrs.items():
                setattr(product, k, v)
            report.products_updated += 1

        variants = {v.sku: v for v in product.variants}
        for r in style_rows:
            variant = variants.get(r.sku)
            if variant is None:
                variant = Variant(sku=r.sku, size=r.size, color=r.color, barcode=r.barcode)
                product.variants.append(variant)
                report.variants_created += 1
            elif (variant.size, variant.color, variant.barcode) != (r.size, r.color, r.barcode):
                variant.size, variant.color, variant.barcode = r.size, r.color, r.barcode
                report.variants_updated += 1

            current = {p.price_list.code: p for p in variant.prices if p.price_list}
            for code, amount in r.prices.items():
                if code in current:
                    if current[code].amount != amount:
                        current[code].amount = amount
                        report.prices_set += 1
                else:
                    variant.prices.append(Price(price_list=lists[code], amount=amount))
                    report.prices_set += 1
    db.flush()


def run(
    db: Session,
    *,
    filename: str,
    content: bytes,
    dry_run: bool,
    actor_id: int | None,
    ip: str | None,
) -> ImportReport:
    lists = {pl.code: pl for pl in db.scalars(select(PriceList))}
    rows, errors = parse(filename, content, set(lists))
    errors += validate(db, rows)

    report = ImportReport(
        dry_run=dry_run, applied=False, rows=len(rows), products_created=0,
        products_updated=0, variants_created=0, variants_updated=0, prices_set=0,
        errors=sorted(errors, key=lambda e: (e.row, e.column or "")),
    )  # fmt: skip
    if errors:
        return report

    apply(db, rows, lists, report)
    if dry_run:
        db.rollback()
        return report

    audit.record(
        db, action="catalog.import", entity="catalog", actor_id=actor_id, ip=ip,
        changes={"file": filename, **report.model_dump(exclude={"errors", "dry_run", "applied"})},
    )  # fmt: skip
    db.commit()
    report.applied = True
    return report


# ---------- Plantilla ----------


def template_xlsx(price_list_codes: list[str]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "catalogo"
    header = [*REQUIRED[:3], "category", "description", "status", *REQUIRED[3:], "barcode"]
    header += [f"price_{code}" for code in price_list_codes]
    ws.append(header)
    example = {
        "style_code": "CAM-OXF-01", "product_name": "Camisa Oxford", "brand": "Retail Ops",
        "category": "camisas", "description": "Camisa manga larga 100% algodón",
        "status": "active", "color": "Blanco", "barcode": "",
    }  # fmt: skip
    for size, sku, b2c in (("S", "CAM-OXF-01-BL-S", 129900), ("M", "CAM-OXF-01-BL-M", 129900)):
        row = {**example, "sku": sku, "size": size, "price_B2C": b2c, "price_B2B": b2c * 0.6}
        ws.append([row.get(h, "") for h in header])
    for index in range(1, len(header) + 1):
        ws.column_dimensions[get_column_letter(index)].width = 18
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
