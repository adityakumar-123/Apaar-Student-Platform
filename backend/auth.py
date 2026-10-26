import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models import User, AuditLog

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-jwt")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter()


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt = stored.split("$")[0]
    return hmac.compare_digest(hash_password(password, salt), stored)


DUMMY_HASH = hash_password("not-a-real-password")


def create_token(user: User) -> str:
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": int(time.time()) + TOKEN_MINUTES * 60,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    error = HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise error
    user = db.query(User).filter_by(username=data.get("sub")).first()
    if not user or not user.is_active:
        raise error
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "This action requires role: " + " or ".join(roles))
        return user

    return checker


def institution_scope(
    institution_code: str = Form(...),
    user: User = Depends(require_roles("institution", "aicte")),
) -> User:
    if user.role == "institution" and user.institution_code != institution_code:
        raise HTTPException(403, "You can only upload data for your own institution")
    return user


@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=form.username).first()
    if user:
        ok = user.is_active and verify_password(form.password, user.password_hash)
    else:
        verify_password(form.password, DUMMY_HASH)  # keeps timing similar
        ok = False

    if not ok:
        db.add(AuditLog(actor=form.username[:50], action="LOGIN_FAILED", details=""))
        db.commit()
        raise HTTPException(401, "Incorrect username or password")

    db.add(AuditLog(actor=user.username, action="LOGIN", details=user.role))
    db.commit()
    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "institution_code": user.institution_code,
    }


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role, "institution_code": user.institution_code}
