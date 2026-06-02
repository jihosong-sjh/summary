from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthRequest, RefreshRequest, TokenPair

router = APIRouter()


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id, user.refresh_token_version),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRequest, db: Session = Depends(get_db)) -> TokenPair:
    email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_pair(user)


@router.post("/login", response_model=TokenPair)
def login(payload: AuthRequest, db: Session = Depends(get_db)) -> TokenPair:
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_pair(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    token = decode_token(payload.refresh_token, "refresh")
    user = db.get(User, token["sub"])
    if user is None or int(token.get("version", -1)) != user.refresh_token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return _token_pair(user)

