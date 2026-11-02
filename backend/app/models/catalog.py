"""Catálogo: categorías, productos (estilos), variantes (SKU talla/color), listas de precio,
precios y cupones.

Modelo de moda: un *producto* es el estilo ("Camisa Oxford"); lo que se vende y se cuenta
en bodega es la *variante* (SKU), una combinación de talla y color. Los precios cuelgan de
la variante y de una lista de precio (B2C, B2B...), así un mismo SKU puede costar distinto
para el cliente final y para el mayorista. Ver docs/adr/0003-modelo-catalogo.md.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

MONEY = Numeric(14, 2)


def _pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class ProductStatus(StrEnum):
    DRAFT = "draft"  # en preparación, no se publica
    ACTIVE = "active"  # visible para la venta
    ARCHIVED = "archived"  # fuera de catálogo; se conserva el historial


class Channel(StrEnum):
    B2C = "b2c"
    B2B = "b2b"


class CouponKind(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    style_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    brand: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        _pg_enum(ProductStatus, "product_status"),
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
        index=True,
    )
    images: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")

    category: Mapped[Category | None] = relationship(lazy="joined")
    variants: Mapped[list["Variant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="Variant.id",
    )


class Variant(TimestampMixin, Base):
    __tablename__ = "variants"
    __table_args__ = (
        UniqueConstraint("product_id", "size", "color", name="uq_variants_product_size_color"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(40))
    barcode: Mapped[str | None] = mapped_column(String(32), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    product: Mapped[Product] = relationship(back_populates="variants")
    prices: Mapped[list["Price"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan", lazy="selectin"
    )


class PriceList(TimestampMixin, Base):
    __tablename__ = "price_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # "B2C", "B2B"
    name: Mapped[str] = mapped_column(String(80))
    channel: Mapped[Channel] = mapped_column(_pg_enum(Channel, "sales_channel"))
    currency: Mapped[str] = mapped_column(String(3), default="COP", server_default="COP")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount_non_negative"),)

    price_list_id: Mapped[int] = mapped_column(
        ForeignKey("price_lists.id", ondelete="CASCADE"), primary_key=True
    )
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    variant: Mapped[Variant] = relationship(back_populates="prices")
    price_list: Mapped[PriceList] = relationship(lazy="joined")


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("value > 0", name="value_positive"),
        CheckConstraint("kind <> 'percent' OR value <= 100", name="percent_max_100"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="valid_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # siempre MAYÚSCULAS
    description: Mapped[str] = mapped_column(String(200), default="", server_default="")
    kind: Mapped[CouponKind] = mapped_column(_pg_enum(CouponKind, "coupon_kind"))
    value: Mapped[Decimal] = mapped_column(MONEY)
    channel: Mapped[Channel | None] = mapped_column(_pg_enum(Channel, "sales_channel"))
    min_subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0), server_default="0")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
