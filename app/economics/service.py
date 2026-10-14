"""Persist economic exposures per document (idempotent)."""

import logging
from uuid import UUID

from sqlalchemy import delete, select

from app.economics.calculator import calculate_economics
from app.storage.database import async_session_maker
from app.storage.models import Clause, ContractFact, EconomicExposure

logger = logging.getLogger(__name__)


class EconomicsService:
    async def calculate_for_document(
        self, document_id: UUID
    ) -> tuple[list[EconomicExposure], list[dict]]:
        async with async_session_maker() as session:
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
            clause_categories = {
                c.category
                for c in (
                    (await session.execute(select(Clause).where(Clause.document_id == document_id)))
                    .scalars()
                    .all()
                )
                if c.category
            }

            result = calculate_economics(facts, clause_categories)

            await session.execute(
                delete(EconomicExposure).where(EconomicExposure.document_id == document_id)
            )
            rows = [
                EconomicExposure(
                    document_id=document_id,
                    scenario=e.scenario,
                    assumption=e.assumption,
                    formula=e.formula,
                    result=e.result,
                    currency=e.currency,
                    source_reference=e.source_reference,
                )
                for e in result.exposures
            ]
            session.add_all(rows)
            await session.commit()
            for r in rows:
                await session.refresh(r)

            notes = [{"metric": c.metric, "reason": c.reason} for c in result.cannot_calculate]
            logger.info(
                "economics for %s: %d exposures, %d cannot-calculate notes",
                document_id,
                len(rows),
                len(notes),
            )
            return rows, notes


economics_service = EconomicsService()
