import uuid

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from sqlalchemy import select

from app.obligations.service import obligations_service
from app.storage.database import async_session_maker
from app.storage.models import Document, DocumentStatus, Obligation

router = APIRouter(prefix="/documents", tags=["obligations"])


@router.post("/{document_id}/obligations", status_code=202)
async def extract_obligations_endpoint(
    document_id: uuid.UUID,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:analyze")),
) -> dict[str, str]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.status != DocumentStatus.EXTRACTED:
            raise HTTPException(
                status_code=409,
                detail=f"Document status is {document.status}; extraction required first",
            )
    # Runs synchronously — extraction is fast and deterministic.
    await obligations_service.extract_for_document(document_id)
    return {"status": "obligations_extracted", "document_id": str(document_id)}


@router.get("/{document_id}/obligations")
async def list_obligations(
    document_id: uuid.UUID,
    party: str | None = None,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),
) -> list[dict]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        stmt = select(Obligation).where(Obligation.document_id == document_id)
        if party is not None:
            stmt = stmt.where(Obligation.party == party)
        obligations = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": str(o.id),
                "party": o.party,
                "obligation": o.obligation,
                "trigger": o.trigger,
                "frequency": o.frequency,
                "source_reference": o.source_reference,
            }
            for o in obligations
        ]
