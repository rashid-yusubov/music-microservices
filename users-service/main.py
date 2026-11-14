from fastapi import FastAPI, HTTPException, status

from models.user import UserCreate, UserResponse
from services.user_service import user_service
from models.user import UserLogin, TokenResponse

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.token_service import (
    verify_access_token,
    revoke_token
)

from database import engine, Base
import models.user_db

security = HTTPBearer()


app = FastAPI(title="Users Service")


@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass


@app.get("/")
def home():
    return {"message": "Users Service is running"}


@app.post(
    "/api/v1/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(data: UserCreate):
    try:
        return user_service.register(data)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )

@app.post(
    "/api/v1/auth/login",
    response_model=TokenResponse
)
def login(data: UserLogin):
    try:
        return user_service.login(data)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error)
        )

@app.post(
    "/api/v1/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT
)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        verify_access_token(token)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error)
        )

    revoke_token(token)
    return None