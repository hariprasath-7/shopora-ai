"""Authentication API handlers."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .cache import rate_limit
from .config import settings
from .database import get_db
from .models import Customer, RefreshToken
from .security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    set_refresh_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def user_response(user: Customer) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role)


def _issue_refresh(db: Session, user: Customer, response: Response) -> None:
    raw, token_hash, expires = create_refresh_token(user.id)
    db.add(RefreshToken(customer_id=user.id, token_hash=token_hash, expires_at=expires))
    db.commit()
    set_refresh_cookie(response, raw)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(Customer).where(Customer.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = Customer(name=payload.name.strip(), email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.flush()
    _issue_refresh(db, user, response)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limit(f"auth:login:{client_ip}", 10, 60):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    email = str(payload.email).lower()
    user = db.scalar(select(Customer).where(Customer.email == email))
    if user is None or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    _issue_refresh(db, user, response)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        raise HTTPException(status_code=401, detail="Refresh session missing")
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None)))
    now = datetime.now(UTC)
    if token is None or token.expires_at <= now or not token.customer.is_active:
        raise HTTPException(status_code=401, detail="Refresh session expired")
    token.revoked_at = now
    _issue_refresh(db, token.customer, response)
    return TokenResponse(access_token=create_access_token(token.customer_id))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.refresh_cookie_name)
    if raw:
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None)))
        if token:
            token.revoked_at = datetime.now(UTC)
            db.commit()
    response.delete_cookie(settings.refresh_cookie_name, path="/auth")


@router.get("/me", response_model=UserResponse)
def me(user: Customer = Depends(get_current_user)):
    return user_response(user)
