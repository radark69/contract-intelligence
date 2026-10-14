import uuid

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from sqlalchemy import select

from app.economics.calculator import calculate_economics
from app.storage.database import async_session_maker
from app.storage.models import Clause, ContractFact, Document, EconomicExposure

router = APIRouter(prefix="/documents", tags=["economics"])


@router.get("/{document_id}/exposures")
async def list_exposures(
    document_id: uuid.UUID,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),
) -> dict:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        rows = (
            (
                await session.execute(
                    select(EconomicExposure).where(EconomicExposure.document_id == document_id)
                )
            )
            .scalars()
            .all()
        )
        facts = {
            f.key: f
            for f in (
                (
                    await session.execute(
                        select(ContractFact).where(ContractFact.document_id == document_id)
                    )
                )
                .scalars()
                .all()
            )
        }
        categories = {
            c.category
            for c in (
                (await session.execute(select(Clause).where(Clause.document_id == document_id)))
                .scalars()
                .all()
            )
            if c.category
        }
        notes = calculate_economics(facts, categories).cannot_calculate

        return {
            "document_id": str(document_id),
            "exposures": [
                {
                    "id": str(r.id),
                    "scenario": r.scenario,
                    "assumption": r.assumption,
                    "formula": r.formula,
                    "result": float(r.result),
                    "currency": r.currency,
                    "source_reference": r.source_reference,
                }
                for r in rows
            ],
            "cannot_calculate": [{"metric": c.metric, "reason": c.reason} for c in notes],
        }
