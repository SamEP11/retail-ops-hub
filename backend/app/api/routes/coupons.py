from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import DbSession, client_ip, require
from app.models import Coupon, User
from app.permissions import Permission
from app.schemas.catalog import CouponCheckIn, CouponCheckOut, CouponIn, CouponOut, CouponUpdate
from app.schemas.common import Page
from app.services import coupons

router = APIRouter(prefix="/coupons", tags=["coupons"])

CanRead = Annotated[User, Depends(require(Permission.CATALOG_READ))]
CanWrite = Annotated[User, Depends(require(Permission.CATALOG_WRITE))]


@router.get("", response_model=Page[CouponOut])
def list_coupons(
    db: DbSession,
    _: CanRead,
    active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CouponOut]:
    stmt = select(Coupon)
    if active is not None:
        stmt = stmt.where(Coupon.is_active.is_(active))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Coupon.id.desc()).limit(limit).offset(offset))
    return Page[CouponOut](
        items=[CouponOut.model_validate(c) for c in rows], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
def create_coupon(data: CouponIn, db: DbSession, actor: CanWrite, request: Request) -> Coupon:
    return coupons.create(db, data, actor_id=actor.id, ip=client_ip(request))


@router.patch("/{coupon_id}", response_model=CouponOut)
def update_coupon(
    coupon_id: int, data: CouponUpdate, db: DbSession, actor: CanWrite, request: Request
) -> Coupon:
    coupon = coupons.get(db, coupon_id)
    return coupons.update(db, coupon, data, actor_id=actor.id, ip=client_ip(request))


@router.post("/check", response_model=CouponCheckOut)
def check_coupon(data: CouponCheckIn, db: DbSession, _: CanRead) -> CouponCheckOut:
    """Calcula el descuento sin consumir el cupón (lo consume el pedido, Sprint 4)."""
    return coupons.check(db, code=data.code, subtotal=data.subtotal, channel=data.channel)
