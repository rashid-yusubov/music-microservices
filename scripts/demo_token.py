"""Выдача тестового пользовательского JWT для локальной демонстрации."""
import argparse
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt


def main():
    parser = argparse.ArgumentParser(description="Создать тестовый JWT с общим секретом")
    parser.add_argument("--user-id", required=True, type=UUID)
    args = parser.parse_args()
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        parser.error("Нужно задать JWT_SECRET_KEY в окружении")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(args.user_id), "iat": now,
                        "exp": now + timedelta(minutes=30)}, secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
