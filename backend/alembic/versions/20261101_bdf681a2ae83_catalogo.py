"""catalogo

Revision ID: bdf681a2ae83
Revises: 6f86ecf2f66d
Create Date: 2026-11-01 21:20:37.705462

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bdf681a2ae83"
down_revision: str | Sequence[str] | None = "6f86ecf2f66d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Los enums se crean una sola vez y las tablas los reutilizan (create_type=False).
# Sin esto, `sales_channel` se intentaría crear dos veces (coupons y price_lists).
product_status = postgresql.ENUM(
    "draft", "active", "archived", name="product_status", create_type=False
)
sales_channel = postgresql.ENUM("b2c", "b2b", name="sales_channel", create_type=False)
coupon_kind = postgresql.ENUM("percent", "fixed", name="coupon_kind", create_type=False)
ENUMS = (product_status, sales_channel, coupon_kind)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
    )
    op.create_index(op.f("ix_categories_slug"), "categories", ["slug"], unique=True)
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=200), server_default="", nullable=False),
        sa.Column("kind", coupon_kind, nullable=False),
        sa.Column("value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("channel", sales_channel, nullable=True),
        sa.Column(
            "min_subtotal", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind <> 'percent' OR value <= 100", name=op.f("ck_coupons_percent_max_100")
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name=op.f("ck_coupons_valid_window")
        ),
        sa.CheckConstraint("value > 0", name=op.f("ck_coupons_value_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coupons")),
    )
    op.create_index(op.f("ix_coupons_code"), "coupons", ["code"], unique=True)
    op.create_table(
        "price_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("channel", sales_channel, nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="COP", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_lists")),
        sa.UniqueConstraint("code", name=op.f("uq_price_lists_code")),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("style_code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("status", product_status, server_default="draft", nullable=False),
        sa.Column(
            "images", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_products_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_index(op.f("ix_products_brand"), "products", ["brand"], unique=False)
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_index(op.f("ix_products_status"), "products", ["status"], unique=False)
    op.create_index(op.f("ix_products_style_code"), "products", ["style_code"], unique=True)
    op.create_table(
        "variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=60), nullable=False),
        sa.Column("size", sa.String(length=20), nullable=False),
        sa.Column("color", sa.String(length=40), nullable=False),
        sa.Column("barcode", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_variants_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_variants")),
        sa.UniqueConstraint("barcode", name=op.f("uq_variants_barcode")),
        sa.UniqueConstraint("product_id", "size", "color", name="uq_variants_product_size_color"),
    )
    op.create_index(op.f("ix_variants_product_id"), "variants", ["product_id"], unique=False)
    op.create_index(op.f("ix_variants_sku"), "variants", ["sku"], unique=True)
    op.create_table(
        "prices",
        sa.Column("price_list_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_prices_amount_non_negative")),
        sa.ForeignKeyConstraint(
            ["price_list_id"],
            ["price_lists.id"],
            name=op.f("fk_prices_price_list_id_price_lists"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.id"],
            name=op.f("fk_prices_variant_id_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("price_list_id", "variant_id", name=op.f("pk_prices")),
    )

    # Datos de referencia: las dos listas de precio que el negocio usa desde el día 1.
    price_lists = sa.table(
        "price_lists",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("channel", sales_channel),
    )
    op.bulk_insert(
        price_lists,
        [
            {"code": "B2C", "name": "Precio al público", "channel": "b2c"},
            {"code": "B2B", "name": "Precio mayorista", "channel": "b2b"},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("prices")
    op.drop_index(op.f("ix_variants_sku"), table_name="variants")
    op.drop_index(op.f("ix_variants_product_id"), table_name="variants")
    op.drop_table("variants")
    op.drop_index(op.f("ix_products_style_code"), table_name="products")
    op.drop_index(op.f("ix_products_status"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_index(op.f("ix_products_brand"), table_name="products")
    op.drop_table("products")
    op.drop_table("price_lists")
    op.drop_index(op.f("ix_coupons_code"), table_name="coupons")
    op.drop_table("coupons")
    op.drop_index(op.f("ix_categories_slug"), table_name="categories")
    op.drop_table("categories")
    bind = op.get_bind()
    for enum in ENUMS:
        enum.drop(bind, checkfirst=True)
