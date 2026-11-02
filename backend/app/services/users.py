from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.security import hash_password
from app.models import User
from app.permissions import Role
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit


class EmailAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Ya existe un usuario con ese email")


class LastAdminError(ConflictError):
    """No se puede desactivar ni degradar al último administrador activo."""

    def __init__(self) -> None:
        super().__init__("Debe quedar al menos un administrador activo")


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


def create(db: Session, data: UserCreate, *, actor_id: int | None, ip: str | None) -> User:
    if get_by_email(db, data.email):
        raise EmailAlreadyExistsError()
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.flush()  # obtiene user.id sin cerrar la transacción
    audit.record(
        db,
        action="user.create",
        entity="user",
        entity_id=user.id,
        actor_id=actor_id,
        changes={"email": user.email, "role": user.role.value},
        ip=ip,
    )
    db.commit()
    return user


def update(db: Session, user: User, data: UserUpdate, *, actor_id: int, ip: str | None) -> User:
    incoming = data.model_dump(exclude_unset=True)
    changes = {
        field: {"from": str(getattr(user, field)), "to": str(new)}
        for field, new in incoming.items()
        if getattr(user, field) != new
    }
    if not changes:
        return user

    # Regla de negocio: siempre debe quedar al menos un admin activo.
    stops_being_admin = (
        user.role == Role.ADMIN
        and user.is_active
        and (
            ("role" in changes and incoming["role"] != Role.ADMIN)
            or ("is_active" in changes and incoming["is_active"] is False)
        )
    )
    if stops_being_admin:
        _ensure_other_active_admin(db, user.id)

    for field in changes:
        setattr(user, field, incoming[field])

    audit.record(
        db,
        action="user.update",
        entity="user",
        entity_id=user.id,
        actor_id=actor_id,
        changes=changes,
        ip=ip,
    )
    db.commit()
    return user


def _ensure_other_active_admin(db: Session, user_id: int) -> None:
    others = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == Role.ADMIN, User.is_active.is_(True), User.id != user_id)
    )
    if not others:
        raise LastAdminError()
