import logging
from datetime import UTC, datetime, time
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clauses.classifier import source_reference
from app.facts.extractor import FACT_LABELS, FactCandidate, TextSpan, extract_facts
from app.storage.database import async_session_maker
from app.storage.models import Clause, ContractFact, Document, DocumentPage

logger = logging.getLogger(__name__)

MONEY_KEYS = {"contract_value", "day_rate", "standby_rate", "ld_rate", "liability_cap"}


class FactsService:
    async def extract_facts_for_document(self, document_id: UUID) -> list[FactCandidate]:
        async with async_session_maker() as session:
            document = await session.get(Document, document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            spans = await self._build_spans(session, document_id)

        candidates = extract_facts(spans) if spans else []

        async with async_session_maker() as session:
            await session.execute(
                delete(ContractFact).where(ContractFact.document_id == document_id)
            )
            for c in candidates:
                session.add(
                    ContractFact(
                        document_id=document_id,
                        clause_id=c.clause_id,
                        key=c.key,
                        label=FACT_LABELS.get(c.key, c.key),
                        value=c.value,
                        raw_value=c.raw_value,
                        confidence=c.confidence,
                        source_reference=c.source_reference,
                        source_text=c.source_text,
                    )
                )
            document = await session.get(Document, document_id)
            if document:
                self._denormalize(document, candidates)
            await session.commit()
            if document:
                await session.refresh(document)
        logger.info("Extracted %d facts for %s", len(candidates), document_id)
        return candidates

    async def _build_spans(self, session: AsyncSession, document_id: UUID) -> list[TextSpan]:
        result = await session.execute(
            select(Clause)
            .where(Clause.document_id == document_id)
            .order_by(Clause.source_page, Clause.source_sheet, Clause.clause_number)
        )
        clauses = result.scalars().all()
        spans = [
            TextSpan(
                text=f"{c.title or ''}\n{c.raw_text}".strip(),
                source_reference=source_reference(
                    page=c.source_page, sheet=c.source_sheet, cell_range=c.source_range
                ),
                clause_id=c.id,
            )
            for c in clauses
            if (c.raw_text or "").strip()
        ]
        if spans:
            return spans

        pages = await session.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        return [
            TextSpan(
                text=p.text,
                source_reference=source_reference(page=p.page_number),
            )
            for p in pages.scalars().all()
            if p.text.strip()
        ]

    def _denormalize(self, document: Document, candidates: list[FactCandidate]) -> None:
        by_key: dict[str, list[FactCandidate]] = {}
        for c in candidates:
            by_key.setdefault(c.key, []).append(c)

        value_facts = by_key.get("contract_value", [])
        if value_facts:
            best = max(value_facts, key=lambda c: c.confidence)
            document.contract_value = best.value.get("amount")
            if best.value.get("currency"):
                document.currency = best.value["currency"]

        if not document.currency:
            votes: dict[str, int] = {}
            for key in MONEY_KEYS:
                for c in by_key.get(key, []):
                    currency = c.value.get("currency") if isinstance(c.value, dict) else None
                    if currency:
                        votes[currency] = votes.get(currency, 0) + 1
            if votes:
                document.currency = max(votes, key=lambda k: votes[k])

        if not document.start_date and "start_date" in by_key:
            document.start_date = self._to_dt(by_key["start_date"][0].value)
        if not document.end_date and "end_date" in by_key:
            document.end_date = self._to_dt(by_key["end_date"][0].value)

    @staticmethod
    def _to_dt(iso_value: object) -> datetime | None:
        if not isinstance(iso_value, str):
            return None
        try:
            parsed = datetime.fromisoformat(iso_value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            try:
                return datetime.combine(
                    datetime.strptime(iso_value, "%Y-%m-%d").date(), time.min, tzinfo=UTC
                )
            except ValueError:
                return None

    async def get_facts(self, document_id: UUID, key: str | None = None) -> list[dict]:
        async with async_session_maker() as session:
            query = (
                select(ContractFact)
                .where(ContractFact.document_id == document_id)
                .order_by(ContractFact.key, ContractFact.confidence.desc())
            )
            if key:
                query = query.where(ContractFact.key == key)
            result = await session.execute(query)
            return [
                {
                    "id": str(f.id),
                    "key": f.key,
                    "label": f.label,
                    "value": f.value,
                    "raw_value": f.raw_value,
                    "confidence": float(f.confidence),
                    "source_reference": f.source_reference,
                    "source_text": f.source_text,
                    "clause_id": str(f.clause_id) if f.clause_id else None,
                }
                for f in result.scalars().all()
            ]


facts_service = FactsService()
