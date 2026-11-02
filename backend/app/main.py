import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import audit, auth, catalog, catalog_import, coupons, health, users
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("app")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backoffice de catálogo, inventario y clientes para una marca de moda.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Asigna un X-Request-ID a cada request y loguea método, ruta, status y duración."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"request_id": request_id})
        response = JSONResponse(
            status_code=500,
            content={"detail": "Error interno", "request_id": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    log.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        },
    )
    return response


@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
    """Traduce los errores de los servicios al código HTTP que les corresponde."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(IntegrityError)
async def integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
    """Red de seguridad: si dos peticiones simultáneas pasan la validación y chocan en un
    UNIQUE de la base, respondemos 409 en lugar de un 500."""
    log.warning("integrity error", extra={"msg_detail": str(exc.orig)})
    return JSONResponse(status_code=409, content={"detail": "Conflicto con un registro existente"})


app.include_router(health.router)
routers = (auth, users, audit, catalog, catalog_import, coupons)
for module in routers:
    router = module.router
    app.include_router(router, prefix="/api/v1")
