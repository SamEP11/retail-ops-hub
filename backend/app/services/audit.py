from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    actor_id: int | None = None,
    changes: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Agrega una entrada de auditoría a la transacción actual.

    No hace commit: el log se guarda junto con el cambio que describe, o no se guarda.
    """
    db.add(
        AuditLog(
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            actor_id=actor_id,
            changes=changes or {},
            ip=ip,
        )
    )
