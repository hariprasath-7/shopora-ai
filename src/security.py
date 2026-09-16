"""Authentication, authorization and token security for Shopora."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Customer

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def _create_token(user_id: int, token_type: str, expires_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(user_id, "access", settings.access_token_expire_minutes)


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(48)
    expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash, expires


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise ValueError
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Customer:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    user_id = decode_access_token(credentials.credentials)
    user = db.scalar(select(Customer).where(Customer.id == user_id, Customer.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=401, detail="User is not active")
    return user


def require_admin(user: Customer = Depends(get_current_user)) -> Customer:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def set_refresh_cookie(response, token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        httponly=True,
        secure=settings.environment == "production",
        samesite=settings.refresh_cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth",
    )
