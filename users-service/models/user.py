from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class User(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    password_hash: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str
    expiresIn: int