from typing import Annotated

from pydantic import BaseModel, StringConstraints

# Texto limpio: sin espacios sobrantes a los lados.
Str = Annotated[str, StringConstraints(strip_whitespace=True)]
# Códigos (SKU, estilo, cupón): sin espacios y en MAYÚSCULAS, así "cam-001 " == "CAM-001".
Code = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=1,
        max_length=60,
        pattern=r"^[A-Za-z0-9._-]+$",
    ),
]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
