import pytest
from pydantic import ValidationError

from app.core.config import DEV_SECRET, Settings


def test_secreto_por_defecto_prohibido_en_produccion():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret=DEV_SECRET)


def test_secreto_corto_rechazado():
    with pytest.raises(ValidationError):
        Settings(jwt_secret="corto")


def test_produccion_con_secreto_propio_es_valida():
    s = Settings(environment="production", jwt_secret="x" * 40)
    assert s.environment == "production"
