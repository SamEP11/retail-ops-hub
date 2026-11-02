"""Reglas de negocio del catálogo: productos, variantes y precios."""

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Category, Price, PriceList, Product, ProductStatus, Variant
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    PriceItem,
    ProductIn,
    ProductOut,
    ProductSummary,
    ProductUpdate,
    VariantIn,
    VariantOut,
    VariantUpdate,
)
from app.services import audit

# ---------- Lecturas ----------


def price_lists_by_code(db: Session) -> dict[str, PriceList]:
    return {pl.code: pl for pl in db.scalars(select(PriceList))}


def variant_out(variant: Variant) -> VariantOut:
    return VariantOut(
        id=variant.id,
        sku=variant.sku,
        size=variant.size,
        color=variant.color,
        barcode=variant.barcode,
        is_active=variant.is_active,
        prices={p.price_list.code: p.amount for p in variant.prices},
    )


def product_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        style_code=product.style_code,
        name=product.name,
        brand=product.brand,
        description=product.description,
        status=product.status,
        category=CategoryOut.model_validate(product.category) if product.category else None,
        images=product.images,
        variants=[variant_out(v) for v in product.variants],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def get_product(db: Session, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants).selectinload(Variant.prices))
    )
    if product is None:
        raise NotFoundError("Producto no encontrado")
    return product


def list_products(
    db: Session,
    *,
    q: str | None,
    category_id: int | None,
    status: ProductStatus | None,
    brand: str | None,
    price_list: str,
    limit: int,
    offset: int,
) -> tuple[list[ProductSummary], int]:
    variant_count = (
        select(func.count(Variant.id)).where(Variant.product_id == Product.id).scalar_subquery()
    )
    min_price = (
        select(func.min(Price.amount))
        .join(Variant, Variant.id == Price.variant_id)
        .join(PriceList, PriceList.id == Price.price_list_id)
        .where(Variant.product_id == Product.id, PriceList.code == price_list)
        .scalar_subquery()
    )
    stmt = select(Product, variant_count.label("variant_count"), min_price.label("min_price"))

    if q:
        like = f"%{q.strip()}%"
        sku_match = exists().where(Variant.product_id == Product.id, Variant.sku.ilike(like))
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.style_code.ilike(like),
                Product.brand.ilike(like),
                sku_match,
            )
        )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if status is not None:
        stmt = stmt.where(Product.status == status)
    if brand:
        stmt = stmt.where(func.lower(Product.brand) == brand.strip().lower())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Product.updated_at.desc(), Product.id.desc()).limit(limit).offset(offset)
    )
    items = [
        ProductSummary(
            id=p.id,
            style_code=p.style_code,
            name=p.name,
            brand=p.brand,
            status=p.status,
            category=CategoryOut.model_validate(p.category) if p.category else None,
            variant_count=count,
            min_price=price,
            image=p.images[0] if p.images else None,
            updated_at=p.updated_at,
        )
        for p, count, price in rows
    ]
    return items, total


# ---------- Categorías ----------


def create_category(db: Session, data: CategoryIn, *, actor_id: int, ip: str | None) -> Category:
    if db.scalar(select(Category).where(Category.slug == data.slug)):
        raise ConflictError(f"Ya existe la categoría '{data.slug}'")
    category = Category(name=data.name, slug=data.slug)
    db.add(category)
    db.flush()
    audit.record(
        db, action="category.create", entity="category", entity_id=category.id,
        actor_id=actor_id, changes=data.model_dump(), ip=ip,
    )  # fmt: skip
    db.commit()
    return category


# ---------- Productos y variantes ----------


def _ensure_category(db: Session, category_id: int | None) -> None:
    if category_id is not None and db.get(Category, category_id) is None:
        raise BusinessRuleError(f"La categoría {category_id} no existe")


def _ensure_unique_variant_keys(
    db: Session, skus: Sequence[str], barcodes: Sequence[str], exclude_variant_id: int | None = None
) -> None:
    stmt = select(Variant.sku, Variant.barcode).where(
        or_(Variant.sku.in_(skus), Variant.barcode.in_([b for b in barcodes if b]))
    )
    if exclude_variant_id is not None:
        stmt = stmt.where(Variant.id != exclude_variant_id)
    clashes = db.execute(stmt).all()
    taken_skus = sorted({sku for sku, _ in clashes if sku in skus})
    taken_barcodes = sorted({bc for _, bc in clashes if bc and bc in barcodes})
    if taken_skus:
        raise ConflictError(f"SKU ya existente: {', '.join(taken_skus)}")
    if taken_barcodes:
        raise ConflictError(f"Código de barras ya existente: {', '.join(taken_barcodes)}")


def _apply_prices(
    db: Session, variant: Variant, prices: Mapping[str, Decimal], lists: Mapping[str, PriceList]
) -> int:
    unknown = sorted(set(prices) - set(lists))
    if unknown:
        raise BusinessRuleError(f"Lista de precio inexistente: {', '.join(unknown)}")
    current = {p.price_list.code: p for p in variant.prices}
    changed = 0
    for code, amount in prices.items():
        if code in current:
            if current[code].amount != amount:
                current[code].amount = amount
                changed += 1
        else:
            variant.prices.append(Price(price_list=lists[code], amount=amount))
            changed += 1
    return changed


def _new_variant(db: Session, data: VariantIn, lists: Mapping[str, PriceList]) -> Variant:
    variant = Variant(sku=data.sku, size=data.size, color=data.color, barcode=data.barcode)
    _apply_prices(db, variant, data.prices, lists)
    return variant


def create_product(db: Session, data: ProductIn, *, actor_id: int, ip: str | None) -> Product:
    if db.scalar(select(Product.id).where(Product.style_code == data.style_code)):
        raise ConflictError(f"Ya existe un producto con código de estilo {data.style_code}")
    _ensure_category(db, data.category_id)
    _ensure_unique_variant_keys(
        db, [v.sku for v in data.variants], [v.barcode for v in data.variants if v.barcode]
    )
    lists = price_lists_by_code(db)

    product = Product(
        style_code=data.style_code,
        name=data.name,
        brand=data.brand,
        description=data.description,
        category_id=data.category_id,
        status=data.status,
        images=[str(url) for url in data.images],
        variants=[_new_variant(db, v, lists) for v in data.variants],
    )
    db.add(product)
    db.flush()
    audit.record(
        db, action="product.create", entity="product", entity_id=product.id, actor_id=actor_id,
        changes={"style_code": product.style_code, "variants": len(product.variants)}, ip=ip,
    )  # fmt: skip
    db.commit()
    return get_product(db, product.id)


def update_product(
    db: Session, product: Product, data: ProductUpdate, *, actor_id: int, ip: str | None
) -> Product:
    incoming = data.model_dump(exclude_unset=True, mode="json")
    if "category_id" in incoming:
        _ensure_category(db, incoming["category_id"])
    if incoming.get("status") == ProductStatus.ACTIVE and not any(
        v.is_active for v in product.variants
    ):
        raise BusinessRuleError("No se puede activar un producto sin variantes activas")

    changes = _diff_and_apply(product, incoming)
    if changes:
        audit.record(
            db, action="product.update", entity="product", entity_id=product.id,
            actor_id=actor_id, changes=changes, ip=ip,
        )  # fmt: skip
        db.commit()
    return get_product(db, product.id)


def add_variant(
    db: Session, product: Product, data: VariantIn, *, actor_id: int, ip: str | None
) -> Variant:
    combo = (data.size.lower(), data.color.lower())
    if any((v.size.lower(), v.color.lower()) == combo for v in product.variants):
        raise ConflictError(f"El producto ya tiene la variante {data.size} / {data.color}")
    _ensure_unique_variant_keys(db, [data.sku], [data.barcode] if data.barcode else [])

    variant = _new_variant(db, data, price_lists_by_code(db))
    product.variants.append(variant)
    db.flush()
    audit.record(
        db, action="variant.create", entity="variant", entity_id=variant.id, actor_id=actor_id,
        changes={"product_id": product.id, "sku": variant.sku}, ip=ip,
    )  # fmt: skip
    db.commit()
    return variant


def get_variant(db: Session, variant_id: int) -> Variant:
    variant = db.get(Variant, variant_id)
    if variant is None:
        raise NotFoundError("Variante no encontrada")
    return variant


def update_variant(
    db: Session, variant: Variant, data: VariantUpdate, *, actor_id: int, ip: str | None
) -> Variant:
    incoming = data.model_dump(exclude_unset=True)
    if incoming.get("barcode"):
        _ensure_unique_variant_keys(db, [], [incoming["barcode"]], exclude_variant_id=variant.id)

    size = incoming.get("size", variant.size).lower()
    color = incoming.get("color", variant.color).lower()
    siblings = db.scalars(
        select(Variant).where(Variant.product_id == variant.product_id, Variant.id != variant.id)
    )
    if any((s.size.lower(), s.color.lower()) == (size, color) for s in siblings):
        raise ConflictError("Ya existe otra variante con esa talla y color")

    changes = _diff_and_apply(variant, incoming)
    if changes:
        audit.record(
            db, action="variant.update", entity="variant", entity_id=variant.id,
            actor_id=actor_id, changes=changes, ip=ip,
        )  # fmt: skip
        db.commit()
    return variant


def _diff_and_apply(obj: object, incoming: Mapping[str, object]) -> dict[str, dict[str, str]]:
    changes: dict[str, dict[str, str]] = {}
    for field, new in incoming.items():
        old = getattr(obj, field)
        if old != new:
            changes[field] = {"from": str(old), "to": str(new)}
            setattr(obj, field, new)
    return changes


# ---------- Precios ----------


def set_prices(
    db: Session, list_code: str, items: Iterable[PriceItem], *, actor_id: int, ip: str | None
) -> tuple[int, list[str]]:
    """Actualiza precios por SKU en una lista. Devuelve (cambiados, skus_desconocidos).

    Todo o nada: si algún SKU no existe no se guarda ningún precio, para que el comercial
    corrija el archivo completo y no quede la lista a medias.
    """
    price_list = db.scalar(select(PriceList).where(PriceList.code == list_code))
    if price_list is None:
        raise NotFoundError(f"Lista de precio {list_code} no encontrada")

    wanted = {item.sku: item.amount for item in items}
    variants = {v.sku: v for v in db.scalars(select(Variant).where(Variant.sku.in_(wanted)))}
    unknown = sorted(set(wanted) - set(variants))
    if unknown:
        return 0, unknown

    lists = {price_list.code: price_list}
    changed = sum(
        _apply_prices(db, variants[sku], {list_code: amt}, lists) for sku, amt in wanted.items()
    )
    if changed:
        audit.record(
            db, action="price.bulk_set", entity="price_list", entity_id=price_list.id,
            actor_id=actor_id, changes={"list": list_code, "changed": changed}, ip=ip,
        )  # fmt: skip
        db.commit()
    return changed, []
