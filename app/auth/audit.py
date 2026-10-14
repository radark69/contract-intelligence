"""Audit logging service - call from anywhere to log sensitive operations."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuditLog
from app.storage.database import async_session_maker


async def audit_log(
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    details: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session: AsyncSession | None = None,
) -> AuditLog:
    """Create an audit log entry. If session provided, adds to it; otherwise creates own transaction."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if session:
        session.add(log)
        await session.flush()
        return log
    async with async_session_maker() as s:
        s.add(log)
        await s.commit()
        await s.refresh(log)
        return log


async def get_audit_logs(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    async with async_session_maker() as session:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        result = await session.execute(stmt)
        return result.scalars().all()