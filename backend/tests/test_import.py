"""Importación masiva de catálogo desde CSV y Excel."""

import io

import pytest
from openpyxl import Workbook, load_workbook

from app.models import AuditLog, Product, Variant
from app.permissions import Role

URL = "/api/v1/catalog/import"
HEADER = "style_code,product_name,brand,category,status,sku,size,color,barcode,price_B2C,price_B2B"
ROWS = [
    "CAM-01,Camisa Oxford,Marca,camisas,active,CAM-01-BL-S,S,Blanco,7701234567890,129900,77940",
    "CAM-01,Camisa Oxford,Marca,camisas,active,CAM-01-BL-M,M,Blanco,,129900,77940",
    "PAN-01,Pantalón Chino,Marca,,draft,PAN-01-KA-30,30,Kaki,,159900,",
]


def csv_file(*rows: str, header: str = HEADER) -> dict:
    content = "\n".join([header, *rows]).encode()
    return {"file": ("catalogo.csv", content, "text/csv")}


@pytest.fixture
def comercial(client, as_role):
    headers = as_role(Role.COMERCIAL)
    client.post("/api/v1/categories", json={"name": "Camisas", "slug": "camisas"}, headers=headers)
    return headers


def test_por_defecto_es_dry_run_y_no_guarda_nada(client, comercial, db):
    r = client.post(URL, files=csv_file(*ROWS), headers=comercial)
    assert r.status_code == 200
    report = r.json()
    assert report["dry_run"] is True and report["applied"] is False
    assert (report["products_created"], report["variants_created"], report["prices_set"]) == (
        2,
        3,
        5,
    )
    assert db.query(Product).count() == 0


def test_importar_aplica_y_audita(client, comercial, db):
    r = client.post(URL, params={"dry_run": False}, files=csv_file(*ROWS), headers=comercial)
    assert r.json()["applied"] is True
    assert db.query(Variant).count() == 3
    camisa = db.query(Product).filter_by(style_code="CAM-01").one()
    assert camisa.category.slug == "camisas"
    assert db.query(AuditLog).filter_by(action="catalog.import").count() == 1


def test_importar_dos_veces_no_duplica(client, comercial):
    client.post(URL, params={"dry_run": False}, files=csv_file(*ROWS), headers=comercial)
    again = client.post(URL, params={"dry_run": False}, files=csv_file(*ROWS), headers=comercial)
    r = again.json()
    created_or_updated = (
        r["products_created"],
        r["products_updated"],
        r["variants_created"],
        r["variants_updated"],
        r["prices_set"],
    )
    assert created_or_updated == (0, 0, 0, 0, 0)


def test_actualiza_precios_y_nombre(client, comercial):
    client.post(URL, params={"dry_run": False}, files=csv_file(*ROWS), headers=comercial)
    changed = [
        ROWS[0].replace("Camisa Oxford", "Camisa Oxford Slim").replace("129900", "99900"),
        ROWS[1].replace("Camisa Oxford", "Camisa Oxford Slim"),
    ]
    r = client.post(URL, params={"dry_run": False}, files=csv_file(*changed), headers=comercial)
    body = r.json()
    assert (body["products_updated"], body["prices_set"]) == (1, 1)


def test_reporta_todos_los_errores_con_fila_y_columna(client, comercial, db):
    rows = [
        ROWS[0],
        # fila 3: nombre distinto al de la fila 2 y precio que no es número
        "CAM-01,Otro nombre,Marca,camisas,active,CAM-01-BL-M,M,Blanco,,abc,",
        # fila 4: categoría, estado, código de barras y SKU inválidos
        "CAM-02,Camisa,Marca,no-existe,activo,CAM-01-BL-S,S,Negro,123,10,",
    ]
    r = client.post(URL, params={"dry_run": False}, files=csv_file(*rows), headers=comercial)
    body = r.json()
    assert body["applied"] is False
    found = {(e["row"], e["column"]) for e in body["errors"]}
    assert {
        (3, "product_name"),
        (3, "price_b2c"),
        (4, "category"),
        (4, "status"),
        (4, "barcode"),
        (4, "sku"),
    } <= found
    assert db.query(Product).count() == 0  # con un error no se guarda nada


def test_sku_de_otro_estilo_en_la_base(client, comercial):
    client.post(URL, params={"dry_run": False}, files=csv_file(*ROWS), headers=comercial)
    stolen = "CAM-99,Otra,Marca,,draft,CAM-01-BL-S,XL,Rojo,,1,"
    errors = client.post(URL, files=csv_file(stolen), headers=comercial).json()["errors"]
    assert errors == [
        {"row": 2, "column": "sku", "message": "El SKU ya pertenece al estilo CAM-01"}
    ]


def test_csv_con_punto_y_coma_de_excel_en_espanol(client, comercial):
    header = HEADER.replace(",", ";")
    rows = [ROWS[2].replace(",", ";")]
    content = ("﻿" + "\n".join([header, *rows])).encode()  # con BOM, como lo guarda Excel
    r = client.post(URL, files={"file": ("c.csv", content, "text/csv")}, headers=comercial)
    assert r.json()["errors"] == []
    assert r.json()["variants_created"] == 1


def test_excel_con_la_plantilla(client, comercial):
    template = client.get(f"{URL}/template", headers=comercial)
    assert template.status_code == 200
    wb = load_workbook(io.BytesIO(template.content))
    header = [c.value for c in wb.active[1]]
    assert header[-2:] == ["price_B2C", "price_B2B"]

    r = client.post(URL, files={"file": ("plantilla.xlsx", template.content)}, headers=comercial)
    body = r.json()
    assert body["errors"] == [] and body["variants_created"] == 2


def test_excel_con_codigo_de_barras_numerico(client, comercial):
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER.split(","))
    ws.append(
        [
            "PAN-01",
            "Pantalón",
            "Marca",
            "",
            "draft",
            "PAN-01-30",
            "30",
            "Kaki",
            7701234567890,
            159900,
            None,
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post(URL, files={"file": ("x.xlsx", buf.getvalue())}, headers=comercial)
    assert r.json()["errors"] == []


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"file": ("a.txt", b"hola")}, "Formato"),
        (csv_file(header="style_code,sku"), "obligatorias"),
        (csv_file(ROWS[0], header=HEADER + ",price_VIP"), "VIP"),
        ({"file": ("vacio.csv", b"")}, "vacío"),
    ],
)
def test_archivo_invalido_da_422(client, comercial, files, message):
    r = client.post(URL, files=files, headers=comercial)
    assert r.status_code == 422
    assert message in r.json()["detail"]


def test_bodega_no_importa(client, as_role):
    r = client.post(URL, files=csv_file(*ROWS), headers=as_role(Role.BODEGA))
    assert r.status_code == 403
