from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.auth import LoginResponse, RegisterRequest, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register", response_model=UserOut, status_code=201, summary="注册本地用户")
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    try:
        user = auth_service.register_user(db, request.username, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.post("/login", response_model=LoginResponse, summary="登录并获取访问令牌")
def login(request: RegisterRequest, db: Session = Depends(get_db)) -> LoginResponse:
    token = auth_service.login(db, request.username, request.password)
    if token is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(access_token=token.token)
