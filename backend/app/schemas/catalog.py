from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models import Channel, CouponKind, ProductStatus
from app.schemas.common import Code, Str

CENT = Decimal("0.01")
# Dinero: Decimal (nunca float) y siempre con 2 decimales, igual que en la base.
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=14, decimal_places=2),
    AfterValidator(lambda v: v.quantize(CENT)),
]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)]


# ---------- Categorías ----------
class CategoryIn(BaseModel):
    name: Str = Field(min_length=2, max_length=80)
    slug: Slug


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Variantes ----------
class VariantIn(BaseModel):
    sku: Code
    size: Str = Field(min_length=1, max_length=20)
    color: Str = Field(min_length=1, max_length=40)
    barcode: Str | None = Field(default=None, pattern=r"^\d{8,14}$")
    prices: dict[Code, Money] = Field(
        default_factory=dict, description="Precio por código de lista, p. ej. {'B2C': 89900}"
    )


class VariantUpdate(BaseModel):
    size: Str | None = Field(default=None, min_length=1, max_length=20)
    color: Str | None = Field(default=None, min_length=1, max_length=40)
    barcode: Str | None = Field(default=None, pattern=r"^\d{8,14}$")
    is_active: bool | None = None


class VariantOut(BaseModel):
    id: int
    sku: str
    size: str
    color: str
    barcode: str | None
    is_active: bool
    prices: dict[str, Decimal]


# ---------- Productos ----------
class ProductIn(BaseModel):
    style_code: Code
    name: Str = Field(min_length=2, max_length=160)
    brand: Str = Field(min_length=1, max_length=80)
    description: Str = Field(default="", max_length=5000)
    category_id: int | None = None
    status: ProductStatus = ProductStatus.DRAFT
    images: list[HttpUrl] = Field(default_factory=list, max_length=12)
    variants: list[VariantIn] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _variantes_sin_duplicados(self) -> Self:
        skus = [v.sku for v in self.variants]
        combos = [(v.size.lower(), v.color.lower()) for v in self.variants]
        if len(set(skus)) != len(skus):
            raise ValueError("Hay SKUs repetidos en las variantes")
        if len(set(combos)) != len(combos):
            raise ValueError("Hay combinaciones talla/color repetidas")
        return self


class ProductUpdate(BaseModel):
    name: Str | None = Field(default=None, min_length=2, max_length=160)
    brand: Str | None = Field(default=None, min_length=1, max_length=80)
    description: Str | None = Field(default=None, max_length=5000)
    category_id: int | None = None
    status: ProductStatus | None = None
    images: list[HttpUrl] | None = Field(default=None, max_length=12)


class ProductSummary(BaseModel):
    id: int
    style_code: str
    name: str
    brand: str
    status: ProductStatus
    category: CategoryOut | None
    variant_count: int
    min_price: Decimal | None = Field(description="Menor precio en la lista consultada")
    image: str | None
    updated_at: datetime


class ProductOut(BaseModel):
    id: int
    style_code: str
    name: str
    brand: str
    description: str
    status: ProductStatus
    category: CategoryOut | None
    images: list[str]
    variants: list[VariantOut]
    created_at: datetime
    updated_at: datetime


# ---------- Precios ----------
class PriceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    channel: Channel
    currency: str
    is_active: bool


class PriceItem(BaseModel):
    sku: Code
    amount: Money


class PriceBulkIn(BaseModel):
    items: list[PriceItem] = Field(min_length=1, max_length=5000)


class PriceBulkOut(BaseModel):
    updated: int
    unknown_skus: list[str]


# ---------- Cupones ----------
class CouponIn(BaseModel):
    code: Code
    description: Str = Field(default="", max_length=200)
    kind: CouponKind
    value: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    channel: Channel | None = Field(default=None, description="None = aplica a ambos canales")
    min_subtotal: Money = Decimal(0)
    starts_at: datetime
    ends_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _reglas(self) -> Self:
        if self.kind is CouponKind.PERCENT and self.value > 100:
            raise ValueError("Un cupón porcentual no puede superar 100")
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at debe ser posterior a starts_at")
        return self


class CouponUpdate(BaseModel):
    description: Str | None = Field(default=None, max_length=200)
    ends_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    description: str
    kind: CouponKind
    value: Decimal
    channel: Channel | None
    min_subtotal: Decimal
    starts_at: datetime
    ends_at: datetime | None
    max_uses: int | None
    used_count: int
    is_active: bool


class CouponCheckIn(BaseModel):
    code: Code
    subtotal: Money
    channel: Channel


class CouponCheckOut(BaseModel):
    valid: bool
    code: str
    discount: Decimal
    total: Decimal
    reason: str | None = None


# ---------- Importación ----------
class ImportIssue(BaseModel):
    row: int = Field(description="Número de fila en el archivo (la 1 es el encabezado)")
    column: str | None
    message: str


class ImportReport(BaseModel):
    dry_run: bool
    applied: bool
    rows: int
    products_created: int
    products_updated: int
    variants_created: int
    variants_updated: int
    prices_set: int
    errors: list[ImportIssue]
