"""Catálogo demo para desarrollo local: una marca de moda pequeña.

Se genera como CSV y se carga con la misma importación que usan los usuarios, así el seed
también ejercita ese código.
"""

from itertools import product as combos

CATEGORIES = [
    ("Camisas", "camisas"),
    ("Pantalones", "pantalones"),
    ("Vestidos", "vestidos"),
    ("Chaquetas", "chaquetas"),
    ("Accesorios", "accesorios"),
]

# style_code, nombre, categoría, estado, tallas, colores, precio B2C
STYLES = [
    ("CAM-OXF", "Camisa Oxford", "camisas", "active", "S M L XL", "Blanco Azul", 129900),
    ("CAM-LIN", "Camisa de lino", "camisas", "active", "S M L", "Beige Blanco", 149900),
    ("CAM-DEN", "Camisa denim", "camisas", "draft", "M L", "Índigo", 159900),
    ("PAN-CHI", "Pantalón chino", "pantalones", "active", "28 30 32 34", "Kaki Negro", 159900),
    ("PAN-JEA", "Jean slim", "pantalones", "active", "28 30 32 34 36", "Azul", 179900),
    ("VES-MID", "Vestido midi", "vestidos", "active", "XS S M", "Negro Terracota", 219900),
    ("VES-CAM", "Vestido camisero", "vestidos", "archived", "S M", "Rayas", 189900),
    ("CHA-DEN", "Chaqueta denim", "chaquetas", "active", "S M L", "Azul", 249900),
    ("CHA-BOM", "Chaqueta bomber", "chaquetas", "draft", "M L XL", "Verde oliva", 289900),
    ("ACC-CIN", "Cinturón de cuero", "accesorios", "active", "U", "Café Negro", 79900),
]

HEADER = "style_code,product_name,brand,category,status,sku,size,color,price_B2C,price_B2B"


def catalog_csv() -> bytes:
    lines = [HEADER]
    for code, name, category, status, sizes, colors, price in STYLES:
        for color, size in combos(colors.split(), sizes.split()):
            sku = f"{code}-{color[:3].upper()}-{size}"
            b2b = round(price * 0.6, -2)  # mayorista: 40 % de descuento, redondeado a centenas
            lines.append(
                f"{code},{name},Retail Ops,{category},{status},{sku},{size},{color},{price},{b2b}"
            )
    return "\n".join(lines).encode()
