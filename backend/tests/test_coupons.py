"""Cupones: reglas como pruebas unitarias (función pura) + integración de la API."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models import Channel, Coupon, CouponKind
from app.permissions import Role
from app.services.coupons import evaluate

NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)


def coupon(**kw) -> Coupon:
    base = dict(
        code="BLACK20",
        kind=CouponKind.PERCENT,
        value=Decimal(20),
        channel=None,
        min_subtotal=Decimal(0),
        starts_at=NOW - timedelta(days=1),
        ends_at=None,
        max_uses=None,
        used_count=0,
        is_active=True,
    )
    return Coupon(**{**base, **kw})


def check(c, subtotal="100000", channel=Channel.B2C):
    return evaluate(c, code="BLACK20", subtotal=Decimal(subtotal), channel=channel, now=NOW)


def test_porcentaje():
    r = check(coupon())
    assert (r.valid, r.discount, r.total) == (True, Decimal("20000.00"), Decimal("80000.00"))


def test_valor_fijo_nunca_deja_total_negativo():
    r = check(coupon(kind=CouponKind.FIXED, value=Decimal(150000)))
    assert (r.discount, r.total) == (Decimal(100000), Decimal(0))


@pytest.mark.parametrize(
    ("kw", "subtotal", "channel", "reason"),
    [
        ({"is_active": False}, "100000", Channel.B2C, "inactivo"),
        ({"starts_at": NOW + timedelta(hours=1)}, "100000", Channel.B2C, "todavía no"),
        ({"ends_at": NOW}, "100000", Channel.B2C, "venció"),
        ({"channel": Channel.B2B}, "100000", Channel.B2C, "B2B"),
        ({"max_uses": 10, "used_count": 10}, "100000", Channel.B2C, "agotó"),
        ({"min_subtotal": Decimal(200000)}, "100000", Channel.B2C, "mínima"),
    ],
)
def test_reglas_de_rechazo(kw, subtotal, channel, reason):
    r = check(coupon(**kw), subtotal, channel)
    assert r.valid is False
    assert r.discount == 0 and r.total == Decimal(subtotal)
    assert reason in r.reason


def test_cupon_inexistente():
    assert check(None).valid is False


# ---------- API ----------


def coupon_payload(**kw):
    return {
        "code": "black20",
        "kind": "percent",
        "value": "20",
        "starts_at": "2026-01-01T00:00:00Z",
        **kw,
    }


def test_crear_y_validar_cupon(client, as_role):
    headers = as_role(Role.COMERCIAL)
    r = client.post("/api/v1/coupons", json=coupon_payload(), headers=headers)
    assert r.status_code == 201
    assert r.json()["code"] == "BLACK20"

    r = client.post(
        "/api/v1/coupons/check",
        json={"code": "black20", "subtotal": "50000", "channel": "b2c"},
        headers=headers,
    )
    assert r.json() == {
        "valid": True,
        "code": "BLACK20",
        "discount": "10000.00",
        "total": "40000.00",
        "reason": None,
    }


@pytest.mark.parametrize(
    "kw",
    [
        {"value": "120"},
        {"value": "0"},
        {"ends_at": "2025-12-31T00:00:00Z"},
        {"code": "con espacio"},
    ],
)
def test_cupon_invalido_da_422(client, as_role, kw):
    r = client.post("/api/v1/coupons", json=coupon_payload(**kw), headers=as_role(Role.COMERCIAL))
    assert r.status_code == 422


def test_codigo_duplicado_da_409(client, as_role):
    headers = as_role(Role.COMERCIAL)
    client.post("/api/v1/coupons", json=coupon_payload(), headers=headers)
    r = client.post("/api/v1/coupons", json=coupon_payload(code="BLACK20"), headers=headers)
    assert r.status_code == 409


def test_desactivar_cupon(client, as_role):
    headers = as_role(Role.COMERCIAL)
    cid = client.post("/api/v1/coupons", json=coupon_payload(), headers=headers).json()["id"]
    r = client.patch(f"/api/v1/coupons/{cid}", json={"is_active": False}, headers=headers)
    assert r.json()["is_active"] is False
    actives = client.get("/api/v1/coupons", params={"active": True}, headers=headers).json()
    assert actives["total"] == 0


def test_bodega_no_crea_cupones(client, as_role):
    r = client.post("/api/v1/coupons", json=coupon_payload(), headers=as_role(Role.BODEGA))
    assert r.status_code == 403
