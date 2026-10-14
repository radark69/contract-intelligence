import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user, require_permission

from app.extraction.service import extraction_service
from app.facts.service import facts_service
from app.obligations.service import obligations_service
from app.risk_engine.service import risk_engine_service
from app.storage.database import async_session_maker
from app.storage.models import Document, DocumentStatus

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["extraction"])


async def _run_extraction(document_id: uuid.UUID) -> None:
    document = await extraction_service.extract_document(document_id)
    if document.status == DocumentStatus.EXTRACTED:
        try:
            await facts_service.extract_facts_for_document(document_id)
        except Exception:
            logger.exception("Fact extraction failed after extraction for %s", document_id)
        try:
            await obligations_service.extract_for_document(document_id)
        except Exception:
            logger.exception("Obligation extraction failed for %s", document_id)
        try:
            await risk_engine_service.analyze_document(document_id)
        except Exception:
            logger.exception("Risk analysis failed after extraction for %s", document_id)


@router.post("/{document_id}/extract", status_code=202)
async def extract_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:extract")),
) -> dict[str, str]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.status == DocumentStatus.PROCESSING:
            raise HTTPException(status_code=409, detail="Extraction already in progress")
    background_tasks.add_task(_run_extraction, document_id)
    return {"id": str(document_id), "status": "processing"}


@router.get("/{document_id}/pages")
async def get_pages(document_id: uuid.UUID) -> list[dict]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
    return await extraction_service.get_pages(document_id)


@router.get("/{document_id}/sheets")
async def get_sheets(
    document_id: uuid.UUID,
    include_data: bool = Query(False),
) -> list[dict]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
    return await extraction_service.get_sheets(document_id, include_data=include_data)


@router.get("/{document_id}/clauses")
async def get_clauses(document_id: uuid.UUID) -> list[dict]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
    return await extraction_service.get_clauses(document_id)
