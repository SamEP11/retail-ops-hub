from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import DbSession, client_ip, require
from app.models import User
from app.permissions import Permission, Role
from app.schemas.user import Page, UserCreate, UserOut, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])

CanRead = Annotated[User, Depends(require(Permission.USERS_READ))]
CanManage = Annotated[User, Depends(require(Permission.USERS_MANAGE))]


@router.get("", response_model=Page[UserOut])
def list_users(
    db: DbSession,
    _: CanRead,
    role: Role | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Busca en email o nombre")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserOut]:
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.full_name).like(like))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.id).limit(limit).offset(offset)).all()
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in rows], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DbSession, actor: CanManage, request: Request) -> User:
    return users.create(db, data, actor_id=actor.id, ip=client_ip(request))


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DbSession, _: CanRead) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, data: UserUpdate, db: DbSession, actor: CanManage, request: Request
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return users.update(db, user, data, actor_id=actor.id, ip=client_ip(request))
