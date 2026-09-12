"""本地账户认证：PBKDF2 密码哈希 + 可撤销的数据库令牌。"""

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import AccessToken, User


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", maxsplit=1)
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$", maxsplit=1)[1]
    return hmac.compare_digest(candidate, digest_hex)


def register_user(db: Session, username: str, password: str) -> User:
    if db.scalar(select(User).where(User.username == username)):
        raise ValueError("用户名已存在")
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, username: str, password: str) -> AccessToken | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return None
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().auth_token_expire_hours)
    token = AccessToken(user_id=user.id, expires_at=expires_at)
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    if not get_settings().auth_enabled:
        return None
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要 Bearer 访问令牌")
    token_value = authorization.removeprefix("Bearer ")
    token = db.get(AccessToken, token_value)
    expires_at = token.expires_at if token else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if token is None or expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="访问令牌无效或已过期")
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
