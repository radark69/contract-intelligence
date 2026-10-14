import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User, UserRole
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.storage.database import async_session_maker

router = APIRouter(prefix="/auth", tags=["auth"])


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: UserRole = UserRole.VIEWER


class UserRead(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


async def _audit(
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    details: str | None = None,
    request: Request | None = None,
):
    from app.auth.models import AuditLog
    async with async_session_maker() as session:
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
        session.add(log)
        await session.commit()


import uuid  # noqa: E402


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, request: Request):
    async with async_session_maker() as session:
        existing = await session.execute(select(User).where(User.email == user_data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    await _audit(user.id, "user.register", "user", user.id, request=request)
    return UserRead(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=Token)
async def login(creds: LoginRequest, request: Request):
    async with async_session_maker() as session:
        user = (await session.execute(select(User).where(User.email == creds.email))).scalar_one_or_none()
        if not user or not verify_password(creds.password, user.hashed_password):
            await _audit(None, "login.failed", details=f"email={creds.email}", request=request)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    await _audit(user.id, "login.success", request=request)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=Token)
async def refresh_token(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if not payload or payload.type != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    async with async_session_maker() as session:
        user = await session.get(User, uuid.UUID(payload.sub))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    return Token(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserRead(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[UserRead])
async def list_users(
    _: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    skip: int = 0,
    limit: int = 50,
):
    async with async_session_maker() as session:
        users = (await session.execute(select(User).offset(skip).limit(limit))).scalars().all()
    return [
        UserRead(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: dict,
    _: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    request: Request,
):
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        for k, v in data.items():
            if k == "password":
                v = hash_password(v)
            if hasattr(user, k):
                setattr(user, k, v)
        user.updated_at = datetime.utcnow()
        await session.commit()
    await _audit(user.id, "user.update", "user", user_id, details=str(data), request=request)
    return {"status": "updated"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    request: Request,
):
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.delete(user)
        await session.commit()
    await _audit(None, "user.delete", "user", user_id, request=request)
    return {"status": "deleted"}