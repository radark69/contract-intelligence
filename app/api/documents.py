import io
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.auth.dependencies import get_current_user, require_permission
from app.auth.file_validation import validate_file_content, is_safe_filename
from app.ingestion.service import ingestion_service
from app.storage.database import async_session_maker
from app.storage.models import Document, DocumentStatus

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    uploaded_by: str | None = Form(None),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:create")),
) -> dict[str, Any]:
    logger.info("Upload request received", filename=file.filename, size=file.size, user=current_user.email)

    if not is_safe_filename(file.filename or ""):
        raise HTTPException(status_code=400, detail="Invalid filename")

    content = await file.read()
    validation = validate_file_content(content, file.filename or "")
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

    file.file = io.BytesIO(content)

    document = await ingestion_service.ingest(file, current_user.email)
    return {
        "id": str(document.id),
        "filename": document.filename,
        "status": document.status.value,
        "file_hash": document.file_hash,
        "document_type": document.document_type.value,
        "created_at": document.created_at.isoformat(),
    }


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),
) -> dict[str, Any]:
    document = await ingestion_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": str(document.id),
        "filename": document.filename,
        "status": document.status.value,
        "file_hash": document.file_hash,
        "document_type": document.document_type.value,
        "file_size": document.file_size,
        "client": document.client,
        "contractor": document.contractor,
        "contract_type": document.contract_type,
        "currency": document.currency,
        "contract_value": float(document.contract_value) if document.contract_value else None,
        "start_date": document.start_date.isoformat() if document.start_date else None,
        "end_date": document.end_date.isoformat() if document.end_date else None,
        "version": document.version,
        "page_count": document.page_count,
        "sheet_count": document.sheet_count,
        "error_message": document.error_message,
        "warnings": document.warnings,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


@router.get("")
async def list_documents(
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),

    skip: int = 0, limit: int = 50, status: DocumentStatus | None = None
) -> list[dict[str, Any]]:
    async with async_session_maker() as session:
        query = select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
        if status:
            query = query.where(Document.status == status)
        result = await session.execute(query)
        documents = result.scalars().all()
        return [
            {
                "id": str(d.id),
                "filename": d.filename,
                "status": d.status.value,
                "document_type": d.document_type.value,
                "client": d.client,
                "contract_value": float(d.contract_value) if d.contract_value else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in documents
        ]


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:delete")),
) -> dict[str, str]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        await session.delete(document)
        await session.commit()
    return {"message": "Document deleted", "id": str(document_id)}
