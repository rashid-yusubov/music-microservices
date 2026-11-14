from uuid import uuid4

from pwdlib import PasswordHash

from models.user import (
    User, UserCreate, UserResponse,
    UserLogin, TokenResponse
)
from repositories.user_repository import user_repository

from services.token_service import (
    create_access_token,
    TOKEN_EXPIRE_SECONDS
)

password_hash = PasswordHash.recommended()


class UserService:

    def register(self, data: UserCreate) -> UserResponse:
        existing_user = user_repository.get_by_email(data.email)

        if existing_user is not None:
            raise ValueError("User with this email already exists")

        new_user = User(
            id=uuid4(),
            username=data.username,
            email=data.email,
            password_hash=password_hash.hash(data.password)
        )

        user_repository.create_user(new_user)

        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email
        )
    def login(self, data: UserLogin) -> TokenResponse:
        user = user_repository.get_by_email(data.email)

        if user is None:
            raise ValueError("Invalid email or password")

        if not password_hash.verify(
            data.password,
            user.password_hash
        ):
            raise ValueError("Invalid email or password")

        token = create_access_token(str(user.id))

        return TokenResponse(
            accessToken=token,
            tokenType="Bearer",
            expiresIn=TOKEN_EXPIRE_SECONDS
        )


user_service = UserService()