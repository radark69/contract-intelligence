import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = 30


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int
    type: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenPayload | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except jwt.PyJWTError:
        return None