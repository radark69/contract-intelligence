import uuid
from datetime import datetime
from typing import Annotated

import os
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.auth.security import decode_token
from app.storage.database import async_session_maker

# Test mode bypass
TESTING = os.getenv("TESTING", "false").lower() == "true"

class _TestUser(User):
    def __init__(self):
        self.id = uuid.uuid4()
        self.email = "test@example.com"
        self.full_name = "Test User"
        self.role = UserRole.ADMIN
        self.is_active = True
        self.created_at = datetime.utcnow()

import uuid
from datetime import datetime

TEST_USER = _TestUser()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User:
    if TESTING:
        return TEST_USER
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if payload is None or payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    async with async_session_maker() as session:
        user = await session.get(User, uuid.UUID(payload.sub))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return user


def require_role(*roles: UserRole):
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


def require_permission(permission: str):
    """Check specific permission - extendable for fine-grained control."""
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        perms = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
        return user

    return checker


ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        "documents:create",
        "documents:read",
        "documents:delete",
        "documents:extract",
        "documents:analyze",
        "documents:download",
        "users:create",
        "users:read",
        "users:update",
        "users:delete",
        "audit:read",
        "system:configure",
    },
    UserRole.REVIEWER: {
        "documents:create",
        "documents:read",
        "documents:extract",
        "documents:analyze",
        "documents:download",
    },
    UserRole.VIEWER: {
        "documents:read",
        "documents:download",
    },
}