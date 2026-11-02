from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession, client_ip
from app.core.config import get_settings
from app.core.ratelimit import LoginLimiter, get_login_limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.permissions import ROLE_PERMISSIONS
from app.schemas.auth import Token
from app.schemas.user import MeOut
from app.services import audit, users

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash de relleno: verificamos contra él cuando el email no existe para que el
# tiempo de respuesta no revele qué correos están registrados.
_DUMMY_HASH = hash_password("relleno-para-tiempo-constante")


@router.post("/login", response_model=Token)
def login(
    db: DbSession,
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    limiter: Annotated[LoginLimiter, Depends(get_login_limiter)],
) -> Token:
    ip = client_ip(request)
    blocked = limiter.check(form.username, ip)
    if blocked:
        audit.record(
            db, action="auth.login_blocked", entity="user",
            changes={"email": form.username.lower()}, ip=ip,
        )  # fmt: skip
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intenta más tarde.",
            headers={"Retry-After": str(blocked.retry_after)},
        )

    user = users.get_by_email(db, form.username)
    password_ok = verify_password(form.password, user.hashed_password if user else _DUMMY_HASH)

    if user is None or not password_ok or not user.is_active:
        limiter.register_failure(form.username, ip)
        audit.record(
            db,
            action="auth.login_failed",
            entity="user",
            changes={"email": form.username.lower()},
            ip=ip,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limiter.reset(form.username)
    audit.record(
        db,
        action="auth.login",
        entity="user",
        entity_id=user.id,
        actor_id=user.id,
        ip=ip,
    )
    db.commit()
    settings = get_settings()
    return Token(
        access_token=create_access_token(str(user.id), user.role.value),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser) -> MeOut:
    return MeOut.model_validate(
        {
            **{
                c: getattr(user, c)
                for c in ("id", "email", "full_name", "role", "is_active", "created_at")
            },
            "permissions": sorted(p.value for p in ROLE_PERMISSIONS[user.role]),
        }
    )
