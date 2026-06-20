from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def generate_token(length: int = 32) -> str:
    return token_urlsafe(length)


def utcnow() -> datetime:
    return datetime.now(UTC)


def token_expires() -> datetime:
    return utcnow() + timedelta(seconds=get_settings().access_token_ttl_seconds)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, int(user_id))


def require_admin_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/auth/login"})
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where((User.username == username) | (User.email == username)))
    if user and user.is_active and verify_password(password, user.password_hash):
        return user
    return None


def form_bool(data: Any) -> bool:
    return str(data).lower() in {"1", "true", "on", "yes"}
