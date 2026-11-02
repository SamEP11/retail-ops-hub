"""Límite de intentos fallidos de login con Redis (ventana fija).

Cada fallo incrementa dos contadores con expiración: uno por email (frena que adivinen la
clave de una cuenta) y uno por IP (frena que prueben muchas cuentas desde un equipo).
Al llegar al límite se responde 429 con Retry-After hasta que expire la ventana.

Si Redis no responde, el login sigue funcionando (fail open) y queda un warning en los
logs: preferimos no dejar a todo el mundo por fuera porque se cayó la caché. La decisión
está en docs/adr/0004-rate-limiting.md.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

import redis

from app.core.config import get_settings

log = logging.getLogger("app.ratelimit")


@lru_cache
def get_redis() -> "redis.Redis":
    settings = get_settings()
    return redis.Redis.from_url(
        settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5, decode_responses=True
    )


@dataclass(frozen=True)
class Blocked:
    retry_after: int  # segundos


class LoginLimiter:
    def __init__(self, client: "redis.Redis") -> None:
        s = get_settings()
        self.client = client
        self.max_per_email = s.login_max_attempts
        self.max_per_ip = s.login_max_attempts_per_ip
        self.window = s.login_window_seconds

    @staticmethod
    def _keys(email: str, ip: str | None) -> list[tuple[str, str]]:
        keys = [("email", f"login:fail:email:{email.lower()}")]
        if ip:
            keys.append(("ip", f"login:fail:ip:{ip}"))
        return keys

    def check(self, email: str, ip: str | None) -> Blocked | None:
        try:
            for kind, key in self._keys(email, ip):
                limit = self.max_per_email if kind == "email" else self.max_per_ip
                count = int(self.client.get(key) or 0)
                if count >= limit:
                    ttl = int(self.client.ttl(key))
                    return Blocked(retry_after=max(ttl, 1))
        except redis.RedisError:
            log.warning("Redis no disponible: login sin rate limiting")
        return None

    def register_failure(self, email: str, ip: str | None) -> None:
        try:
            pipe = self.client.pipeline()
            for _, key in self._keys(email, ip):
                pipe.incr(key)
                pipe.expire(key, self.window, nx=True)  # la ventana arranca con el 1er fallo
            pipe.execute()
        except redis.RedisError:
            log.warning("Redis no disponible: no se registró el intento fallido")

    def reset(self, email: str) -> None:
        try:
            self.client.delete(f"login:fail:email:{email.lower()}")
        except redis.RedisError:
            log.warning("Redis no disponible: no se limpió el contador de login")


def get_login_limiter() -> LoginLimiter:
    return LoginLimiter(get_redis())
