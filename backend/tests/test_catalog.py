"""Integración: categorías, productos, variantes y precios."""

import pytest

from app.models import AuditLog
from app.permissions import Role

API = "/api/v1"


def product_payload(**overrides):
    base = {
        "style_code": "cam-oxf-01",  # se normaliza a MAYÚSCULAS
        "name": "Camisa Oxford",
        "brand": "Retail Ops",
        "status": "active",
        "variants": [
            {
                "sku": "CAM-OXF-01-BL-S",
                "size": "S",
                "color": "Blanco",
                "barcode": "7701234567890",
                "prices": {"B2C": "129900", "B2B": "77940"},
            },
            {"sku": "CAM-OXF-01-BL-M", "size": "M", "color": "Blanco", "prices": {"B2C": "119900"}},
        ],
    }
    return {**base, **overrides}


@pytest.fixture
def comercial(as_role):
    return as_role(Role.COMERCIAL)


@pytest.fixture
def category(client, comercial):
    r = client.post(
        f"{API}/categories", json={"name": "Camisas", "slug": "camisas"}, headers=comercial
    )
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def product(client, comercial, category):
    r = client.post(
        f"{API}/products", json=product_payload(category_id=category["id"]), headers=comercial
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_producto_con_variantes_y_precios(product):
    assert product["style_code"] == "CAM-OXF-01"
    assert product["category"]["slug"] == "camisas"
    s, m = product["variants"]
    assert s["prices"] == {"B2C": "129900.00", "B2B": "77940.00"}
    assert m["prices"] == {"B2C": "119900.00"}


def test_crear_producto_queda_auditado(product, db):
    log = db.query(AuditLog).filter_by(action="product.create").one()
    assert log.changes == {"style_code": "CAM-OXF-01", "variants": 2}


@pytest.mark.parametrize("role", [Role.BODEGA, Role.ANALISTA])
def test_roles_de_solo_lectura_ven_pero_no_editan(client, as_role, product, role):
    headers = as_role(role)
    assert client.get(f"{API}/products/{product['id']}", headers=headers).status_code == 200
    payload = product_payload(style_code="OTRO-1", variants=[])
    assert client.post(f"{API}/products", json=payload, headers=headers).status_code == 403


def test_listado_con_busqueda_por_sku_y_precio_minimo(client, comercial, product):
    r = client.get(f"{API}/products", params={"q": "oxf-01-bl-m"}, headers=comercial)
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["variant_count"] == 2
    assert item["min_price"] == "119900.00"

    b2b = client.get(f"{API}/products", params={"price_list": "b2b"}, headers=comercial).json()
    assert b2b["items"][0]["min_price"] == "77940.00"


def test_filtros_por_estado_y_marca(client, comercial, product):
    client.post(
        f"{API}/products",
        json=product_payload(style_code="PANT-1", brand="Otra", status="draft", variants=[]),
        headers=comercial,
    )
    drafts = client.get(f"{API}/products", params={"status": "draft"}, headers=comercial).json()
    assert [p["style_code"] for p in drafts["items"]] == ["PANT-1"]
    marca = client.get(f"{API}/products", params={"brand": "retail ops"}, headers=comercial).json()
    assert [p["style_code"] for p in marca["items"]] == ["CAM-OXF-01"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"style_code": "CAM-OXF-01", "variants": []}, "código de estilo"),
        (
            {
                "style_code": "X-2",
                "variants": [{"sku": "CAM-OXF-01-BL-S", "size": "L", "color": "Azul"}],
            },
            "SKU ya existente",
        ),
        (
            {
                "style_code": "X-3",
                "variants": [
                    {"sku": "X-3-L", "size": "L", "color": "Azul", "barcode": "7701234567890"}
                ],
            },
            "Código de barras",
        ),
    ],
)
def test_duplicados_dan_409(client, comercial, product, overrides, message):
    r = client.post(f"{API}/products", json=product_payload(**overrides), headers=comercial)
    assert r.status_code == 409
    assert message in r.json()["detail"]


def test_variantes_repetidas_en_el_mismo_payload_dan_422(client, comercial):
    v = {"sku": "A-1", "size": "S", "color": "Negro"}
    payload = product_payload(style_code="A", variants=[v, {**v, "sku": "A-2"}])
    r = client.post(f"{API}/products", json=payload, headers=comercial)
    assert r.status_code == 422


def test_lista_de_precio_inexistente_da_422(client, comercial):
    payload = product_payload(
        variants=[{"sku": "A-1", "size": "S", "color": "N", "prices": {"VIP": "10"}}]
    )
    r = client.post(f"{API}/products", json=payload, headers=comercial)
    assert r.status_code == 422
    assert "VIP" in r.json()["detail"]


def test_no_se_activa_un_producto_sin_variantes(client, comercial):
    r = client.post(
        f"{API}/products", json=product_payload(status="draft", variants=[]), headers=comercial
    )
    pid = r.json()["id"]
    r = client.patch(f"{API}/products/{pid}", json={"status": "active"}, headers=comercial)
    assert r.status_code == 422


def test_agregar_y_editar_variante(client, comercial, product):
    url = f"{API}/products/{product['id']}/variants"
    r = client.post(
        url, json={"sku": "CAM-OXF-01-AZ-S", "size": "S", "color": "Azul"}, headers=comercial
    )
    assert r.status_code == 201
    vid = r.json()["id"]

    dup = client.post(url, json={"sku": "OTRO", "size": "s", "color": "azul"}, headers=comercial)
    assert dup.status_code == 409  # misma talla/color sin importar mayúsculas

    r = client.patch(f"{API}/variants/{vid}", json={"is_active": False}, headers=comercial)
    assert r.json()["is_active"] is False


def test_carga_masiva_de_precios_es_todo_o_nada(client, comercial, product):
    url = f"{API}/price-lists/b2b/prices"
    bad = {
        "items": [
            {"sku": "CAM-OXF-01-BL-M", "amount": "70000"},
            {"sku": "NO-EXISTE", "amount": "1"},
        ]
    }
    r = client.put(url, json=bad, headers=comercial)
    assert r.json() == {"updated": 0, "unknown_skus": ["NO-EXISTE"]}
    detail = client.get(f"{API}/products/{product['id']}", headers=comercial).json()
    assert "B2B" not in detail["variants"][1]["prices"]  # no se guardó nada

    good = {"items": [{"sku": "CAM-OXF-01-BL-M", "amount": "70000"}]}
    assert client.put(url, json=good, headers=comercial).json()["updated"] == 1
    detail = client.get(f"{API}/products/{product['id']}", headers=comercial).json()
    assert detail["variants"][1]["prices"]["B2B"] == "70000.00"


def test_precio_negativo_rechazado(client, comercial, product):
    r = client.put(
        f"{API}/price-lists/B2C/prices",
        json={"items": [{"sku": "CAM-OXF-01-BL-M", "amount": "-1"}]},
        headers=comercial,
    )
    assert r.status_code == 422


def test_listas_de_precio_por_defecto(client, comercial):
    codes = [pl["code"] for pl in client.get(f"{API}/price-lists", headers=comercial).json()]
    assert codes == ["B2C", "B2B"]


def test_producto_inexistente_da_404(client, comercial):
    assert client.get(f"{API}/products/999", headers=comercial).status_code == 404
