from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession, response: Response) -> dict[str, str]:
    """Lo usan Docker, el balanceador y el monitoreo para saber si la API está viva."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "down"}
    return {"status": "ok", "database": "up"}
