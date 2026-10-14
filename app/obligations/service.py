"""Obligation extraction persistence (idempotent per document)."""

import logging
from uuid import UUID

from sqlalchemy import delete, select

from app.obligations.extractor import extract_obligations
from app.storage.database import async_session_maker
from app.storage.models import Clause, Obligation

logger = logging.getLogger(__name__)


class ObligationsService:
    async def extract_for_document(self, document_id: UUID) -> list[Obligation]:
        async with async_session_maker() as session:
            clauses = list(
                (await session.execute(select(Clause).where(Clause.document_id == document_id)))
                .scalars()
                .all()
            )
            extracted = extract_obligations(clauses)

            await session.execute(delete(Obligation).where(Obligation.document_id == document_id))
            rows = [
                Obligation(
                    document_id=document_id,
                    party=o.party,
                    obligation=o.obligation,
                    trigger=o.trigger,
                    frequency=o.frequency,
                    required_evidence=None,
                    consequence=None,
                    source_reference=o.source_reference,
                )
                for o in extracted
            ]
            session.add_all(rows)
            await session.commit()
            for r in rows:
                await session.refresh(r)

            logger.info("extracted %d obligations for %s", len(rows), document_id)
            return rows


obligations_service = ObligationsService()
