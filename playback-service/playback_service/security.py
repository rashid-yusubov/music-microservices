from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from .errors import ApiError


def current_user(authorization: str | None, secret: str) -> UUID:
    if not secret:
        raise ApiError(503, "ConfigurationError", "JWT_SECRET_KEY не задан")
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "Unauthorized", "Требуется Bearer JWT")
    try:
        claims = jwt.decode(authorization[len("Bearer "):].strip(), secret,
                            algorithms=["HS256"], options={"require": ["exp"]})
        return UUID(str(claims.get("sub") or claims.get("userId")))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise ApiError(401, "Unauthorized", "Недействительный JWT или идентификатор пользователя")


def service_bearer(secret: str) -> str:
    if not secret:
        raise ApiError(503, "ConfigurationError", "JWT_SECRET_KEY не задан")
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "playback-service", "role": "service",
        "iat": now, "exp": now + timedelta(minutes=2),
    }
    return "Bearer " + jwt.encode(claims, secret, algorithm="HS256")
