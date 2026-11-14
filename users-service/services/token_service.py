import os
from datetime import datetime, timedelta, timezone

import jwt

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

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "default-dev-secret-key-change-me")

ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 1800


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=TOKEN_EXPIRE_SECONDS
    )

    payload = {
        "sub": user_id,
        "exp": expires_at
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

revoked_tokens: set[str] = set()


def revoke_token(token: str) -> None:
    revoked_tokens.add(token)


def verify_access_token(token: str) -> dict:
    if token in revoked_tokens:
        raise ValueError("Token has been revoked")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload
    except jwt.InvalidTokenError:
        raise ValueError("Invalid or expired token")