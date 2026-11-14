import os
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


security = HTTPBearer(auto_error=False)

from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env, если доступен
for env_candidate in (
    Path(__file__).resolve().parents[2] / ".env",
    Path(__file__).resolve().parents[1] / ".env",
    Path.cwd() / ".env",
):
    if env_candidate.exists():
        load_dotenv(env_candidate, override=False)
        break

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-dev-secret-key-change-me")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> UUID:

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=["HS256"]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise ValueError("Missing user ID")

        return UUID(user_id)

    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )