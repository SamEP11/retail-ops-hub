"""Errores de dominio.

Los servicios lanzan estos errores (sin saber nada de HTTP) y un manejador global en
main.py los traduce al código de estado correcto. Así ningún endpoint repite try/except.
"""


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    """El pedido es válido pero choca con el estado actual (duplicados, reglas de negocio)."""

    status_code = 409


class BusinessRuleError(DomainError):
    """Datos bien formados que el negocio no acepta (p. ej. lista de precio inexistente)."""

    status_code = 422
