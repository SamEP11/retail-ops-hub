"""Catálogo: categorías, productos, variantes y precios."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select

from app.api.deps import DbSession, client_ip, require
from app.models import Category, PriceList, ProductStatus, User
from app.permissions import Permission
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    PriceBulkIn,
    PriceBulkOut,
    PriceListOut,
    ProductIn,
    ProductOut,
    ProductSummary,
    ProductUpdate,
    VariantIn,
    VariantOut,
    VariantUpdate,
)
from app.schemas.common import Page
from app.services import catalog

router = APIRouter(tags=["catalog"])

CanRead = Annotated[User, Depends(require(Permission.CATALOG_READ))]
CanWrite = Annotated[User, Depends(require(Permission.CATALOG_WRITE))]


# ---------- Categorías ----------
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession, _: CanRead) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)))


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryIn, db: DbSession, actor: CanWrite, request: Request) -> Category:
    return catalog.create_category(db, data, actor_id=actor.id, ip=client_ip(request))


# ---------- Productos ----------
@router.get("/products", response_model=Page[ProductSummary])
def list_products(
    db: DbSession,
    _: CanRead,
    q: Annotated[
        str | None, Query(max_length=100, description="Nombre, estilo, marca o SKU")
    ] = None,
    category_id: int | None = None,
    status_: Annotated[ProductStatus | None, Query(alias="status")] = None,
    brand: Annotated[str | None, Query(max_length=80)] = None,
    price_list: Annotated[str, Query(description="Lista para calcular min_price")] = "B2C",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProductSummary]:
    items, total = catalog.list_products(
        db, q=q, category_id=category_id, status=status_, brand=brand,
        price_list=price_list.upper(), limit=limit, offset=offset,
    )  # fmt: skip
    return Page[ProductSummary](items=items, total=total, limit=limit, offset=offset)


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductIn, db: DbSession, actor: CanWrite, request: Request) -> ProductOut:
    product = catalog.create_product(db, data, actor_id=actor.id, ip=client_ip(request))
    return catalog.product_out(product)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession, _: CanRead) -> ProductOut:
    return catalog.product_out(catalog.get_product(db, product_id))


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, data: ProductUpdate, db: DbSession, actor: CanWrite, request: Request
) -> ProductOut:
    product = catalog.get_product(db, product_id)
    updated = catalog.update_product(db, product, data, actor_id=actor.id, ip=client_ip(request))
    return catalog.product_out(updated)


# ---------- Variantes ----------
@router.post(
    "/products/{product_id}/variants",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
)
def add_variant(
    product_id: int, data: VariantIn, db: DbSession, actor: CanWrite, request: Request
) -> VariantOut:
    product = catalog.get_product(db, product_id)
    variant = catalog.add_variant(db, product, data, actor_id=actor.id, ip=client_ip(request))
    return catalog.variant_out(variant)


@router.patch("/variants/{variant_id}", response_model=VariantOut)
def update_variant(
    variant_id: int, data: VariantUpdate, db: DbSession, actor: CanWrite, request: Request
) -> VariantOut:
    variant = catalog.get_variant(db, variant_id)
    updated = catalog.update_variant(db, variant, data, actor_id=actor.id, ip=client_ip(request))
    return catalog.variant_out(updated)


# ---------- Listas de precio ----------
@router.get("/price-lists", response_model=list[PriceListOut])
def list_price_lists(db: DbSession, _: CanRead) -> list[PriceList]:
    return list(db.scalars(select(PriceList).order_by(PriceList.id)))


@router.put("/price-lists/{code}/prices", response_model=PriceBulkOut)
def set_prices(
    code: str, data: PriceBulkIn, db: DbSession, actor: CanWrite, request: Request
) -> PriceBulkOut:
    """Carga masiva de precios por SKU. Si algún SKU no existe, no se guarda nada."""
    updated, unknown = catalog.set_prices(
        db, code.upper(), data.items, actor_id=actor.id, ip=client_ip(request)
    )
    return PriceBulkOut(updated=updated, unknown_skus=unknown)
