"""Configuración leída de variables de entorno (12-factor).

Nunca pongas secretos en el código: todo valor sensible viene de .env o del entorno.
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "solo-para-desarrollo-local-cambiar-en-produccion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Retail Ops Hub API"
    environment: str = Field(default="local", description="local | test | staging | production")
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/retail_ops"

    jwt_secret: str = Field(default=DEV_SECRET, min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _no_default_secret_outside_local(self) -> "Settings":
        if self.environment not in {"local", "test"} and self.jwt_secret == DEV_SECRET:
            raise ValueError("Define JWT_SECRET: el valor por defecto solo sirve en local")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
