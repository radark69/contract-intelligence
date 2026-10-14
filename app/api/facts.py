import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user, require_permission

from app.facts.service import facts_service
from app.storage.database import async_session_maker
from app.storage.models import Document, DocumentStatus

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["facts"])


async def _run_facts(document_id: uuid.UUID) -> None:
    try:
        await facts_service.extract_facts_for_document(document_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Fact extraction failed for %s", document_id)


@router.post("/{document_id}/facts", status_code=202)
async def extract_facts(
    document_id: uuid.UUID, background_tasks: BackgroundTasks
) -> dict[str, str]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.status not in (DocumentStatus.EXTRACTED, DocumentStatus.ANALYZED):
            raise HTTPException(
                status_code=409,
                detail="Document must be extracted before fact extraction",
            )
    background_tasks.add_task(_run_facts, document_id)
    return {"id": str(document_id), "status": "processing"}


@router.get("/{document_id}/facts")
async def get_facts(
    document_id: uuid.UUID,
    key: str | None = Query(None, description="Filter by fact key"),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),
) -> list[dict]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
    return await facts_service.get_facts(document_id, key=key)
