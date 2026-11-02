"""Cupones: creación y cálculo del descuento."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Channel, Coupon, CouponKind
from app.schemas.catalog import CouponCheckOut, CouponIn, CouponUpdate
from app.services import audit

CENT = Decimal("0.01")


def get(db: Session, coupon_id: int) -> Coupon:
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise NotFoundError("Cupón no encontrado")
    return coupon


def create(db: Session, data: CouponIn, *, actor_id: int, ip: str | None) -> Coupon:
    if db.scalar(select(Coupon.id).where(Coupon.code == data.code)):
        raise ConflictError(f"Ya existe el cupón {data.code}")
    coupon = Coupon(**data.model_dump())
    db.add(coupon)
    db.flush()
    audit.record(
        db, action="coupon.create", entity="coupon", entity_id=coupon.id, actor_id=actor_id,
        changes=data.model_dump(mode="json"), ip=ip,
    )  # fmt: skip
    db.commit()
    return coupon


def update(
    db: Session, coupon: Coupon, data: CouponUpdate, *, actor_id: int, ip: str | None
) -> Coupon:
    incoming = data.model_dump(exclude_unset=True)
    ends_at = incoming.get("ends_at", coupon.ends_at)
    if ends_at and ends_at <= coupon.starts_at:
        raise BusinessRuleError("ends_at debe ser posterior a starts_at")

    changes = {}
    for field, new in incoming.items():
        if getattr(coupon, field) != new:
            changes[field] = {"from": str(getattr(coupon, field)), "to": str(new)}
            setattr(coupon, field, new)
    if changes:
        audit.record(
            db, action="coupon.update", entity="coupon", entity_id=coupon.id,
            actor_id=actor_id, changes=changes, ip=ip,
        )  # fmt: skip
        db.commit()
    return coupon


def evaluate(
    coupon: Coupon | None,
    *,
    code: str,
    subtotal: Decimal,
    channel: Channel,
    now: datetime | None = None,
) -> CouponCheckOut:
    """Función pura: decide si el cupón aplica y cuánto descuenta. No escribe nada.

    Se separa de la BD para probar cada regla con tests unitarios rápidos.
    """
    now = now or datetime.now(UTC)

    def rejected(reason: str) -> CouponCheckOut:
        return CouponCheckOut(
            valid=False, code=code, discount=Decimal(0), total=subtotal, reason=reason
        )

    if coupon is None or not coupon.is_active:
        return rejected("Cupón inexistente o inactivo")
    if now < coupon.starts_at:
        return rejected("El cupón todavía no está vigente")
    if coupon.ends_at and now >= coupon.ends_at:
        return rejected("El cupón ya venció")
    if coupon.channel and coupon.channel != channel:
        return rejected(f"El cupón solo aplica para el canal {coupon.channel.value.upper()}")
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return rejected("El cupón agotó sus usos")
    if subtotal < coupon.min_subtotal:
        return rejected(f"Compra mínima de {coupon.min_subtotal:,.0f}")

    if coupon.kind is CouponKind.PERCENT:
        discount = (subtotal * coupon.value / 100).quantize(CENT, ROUND_HALF_UP)
    else:
        discount = coupon.value
    discount = min(discount, subtotal)  # nunca un total negativo
    return CouponCheckOut(valid=True, code=code, discount=discount, total=subtotal - discount)


def check(db: Session, *, code: str, subtotal: Decimal, channel: Channel) -> CouponCheckOut:
    coupon = db.scalar(select(Coupon).where(Coupon.code == code))
    return evaluate(coupon, code=code, subtotal=subtotal, channel=channel)
