# ADR 0004 — Rate limiting del login y arquitectura del panel web

**Estado:** aceptada · **Fecha:** 2026-11-01

## Rate limiting

**Decisión:** contadores de intentos fallidos en Redis con ventana fija de 15 minutos:
5 por email y 20 por IP. Al superar el límite se responde **429** con `Retry-After`,
incluso si la contraseña es correcta. Un login exitoso reinicia el contador del email.

- Por email frena que adivinen la clave de una cuenta; por IP, que prueben muchas cuentas.
- **Fail open:** si Redis no responde, el login funciona sin límite y queda un warning en
  los logs. Alternativa (fail closed) descartada: una caída de Redis dejaría a toda la
  empresa sin acceso.
- Los bloqueos quedan en auditoría (`auth.login_blocked`).

## Panel web

**Decisión:** SPA en React 19 + TypeScript + Vite, con TanStack Query para datos del
servidor, React Router y Tailwind CSS 4.

- **Un solo origen:** en desarrollo Vite reenvía `/api` al backend y en producción lo hace
  nginx. El navegador nunca llama a otro dominio, así que no hay que configurar CORS.
- **TanStack Query** maneja caché, reintentos, carga y errores; no se usa un store global.
  El único estado global es la sesión (`AuthContext`).
- **Token en `localStorage`.** Es simple, pero un XSS podría leerlo. Mitigación: React escapa
  todo lo que renderiza y el token dura 30 minutos. Mejora futura: cookie `httpOnly` con
  refresh token.
- **Los permisos en el frontend solo ocultan botones**; la seguridad real la aplica la API.
- **Filtros en la URL** (`?q=jean&status=active`): se pueden compartir y sobreviven a F5.
- **Imagen de producción:** build en Node y archivos estáticos servidos por nginx (sin Node).
