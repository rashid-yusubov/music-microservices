from uuid import UUID

from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.user import User
from models.user_db import UserDB


class UserRepository:

    def create_user(self, user: User) -> User:
        with SessionLocal() as db:
            db_user = UserDB(
                id=user.id,
                username=user.username,
                email=user.email,
                password_hash=user.password_hash
            )

            db.add(db_user)

            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise ValueError(
                    "User with this email already exists"
                )

            return user

    def get_by_email(self, email: str) -> User | None:
        with SessionLocal() as db:
            db_user = (
                db.query(UserDB)
                .filter(UserDB.email == email)
                .first()
            )

            if db_user is None:
                return None

            return User(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                password_hash=db_user.password_hash
            )

    def get_by_id(self, user_id: UUID) -> User | None:
        with SessionLocal() as db:
            db_user = db.get(UserDB, user_id)

            if db_user is None:
                return None

            return User(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                password_hash=db_user.password_hash
            )


user_repository = UserRepository()