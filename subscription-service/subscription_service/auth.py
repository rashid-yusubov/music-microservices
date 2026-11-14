from uuid import UUID

import jwt

from .errors import ApiError


def authenticated_user(authorization: str | None, secret: str) -> UUID:
    if not secret:
        raise ApiError(503, "ConfigurationError", "JWT_SECRET_KEY не задан")
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "Unauthorized", "Требуется Bearer JWT")
    token = authorization[len("Bearer "):].strip()
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp"]})
        user_id = UUID(str(claims.get("sub") or claims.get("userId")))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise ApiError(401, "Unauthorized", "Недействительный JWT или идентификатор пользователя")
    return user_id


def verify_service_or_user(authorization: str | None, secret: str) -> dict | None:
    """Проверяет JWT токен при его передаче (поддерживает как пользовательские, так и сервисные токены)."""
    if not authorization:
        return None
    if not secret:
        raise ApiError(503, "ConfigurationError", "JWT_SECRET_KEY не задан")
    if not authorization.startswith("Bearer "):
        raise ApiError(401, "Unauthorized", "Требуется Bearer JWT")
    token = authorization[len("Bearer "):].strip()
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp"]})
    except (jwt.PyJWTError, ValueError, TypeError):
        raise ApiError(401, "Unauthorized", "Недействительный JWT токен")
