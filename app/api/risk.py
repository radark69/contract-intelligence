import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user, require_permission
from sqlalchemy import select

from app.playbook.loader import get_playbook
from app.risk_engine.matcher import SEVERITY_ORDER
from app.risk_engine.service import risk_engine_service
from app.storage.database import async_session_maker
from app.storage.models import Document, DocumentStatus, Finding

logger = structlog.get_logger()

router = APIRouter(prefix="/documents", tags=["risk"])


async def _run_analysis(document_id: uuid.UUID) -> None:
    try:
        await risk_engine_service.analyze_document(document_id)
    except Exception:
        logger.exception("Risk analysis failed for %s", document_id)


def _sort_key(f: Finding) -> int:
    return SEVERITY_ORDER.index(f.severity)


@router.post("/{document_id}/analyze", status_code=202)
async def analyze_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(_run_analysis, document_id)
    return {"status": "analysis_queued", "document_id": str(document_id)}


@router.get("/{document_id}/findings")
async def list_findings(
    document_id: uuid.UUID,
    severity: str | None = None,
    rule: str | None = Query(default=None, alias="dbs_policy_rule"),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),
) -> list[dict]:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        stmt = select(Finding).where(Finding.document_id == document_id)
        if severity is not None:
            stmt = stmt.where(Finding.severity == severity)
        if rule is not None:
            stmt = stmt.where(Finding.dbs_policy_rule == rule.upper())
        findings = (await session.execute(stmt)).scalars().all()

        findings = sorted(findings, key=_sort_key)
        return [
            {
                "id": str(f.id),
                "clause_id": str(f.clause_id) if f.clause_id else None,
                "category": str(f.category),
                "severity": str(f.severity),
                "confidence": float(f.confidence),
                "finding": f.finding,
                "risk": f.risk,
                "impact": f.impact,
                "recommendation": f.recommendation,
                "dbs_policy_rule": f.dbs_policy_rule,
                "source_reference": f.source_reference,
                "source_text": f.source_text,
                "financial_impact": float(f.financial_impact)
                if f.financial_impact is not None
                else None,
            }
            for f in findings
        ]


@router.get("/{document_id}/risk-register")
async def risk_register(
    document_id: uuid.UUID,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:read")),
) -> dict:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        findings = (
            (await session.execute(select(Finding).where(Finding.document_id == document_id)))
            .scalars()
            .all()
        )
        findings = sorted(findings, key=_sort_key)

        rows = []
        for f in findings:
            rows.append(
                {
                    "id": str(f.id),
                    "severity": str(f.severity),
                    "category": str(f.category),
                    "clause": f.source_reference,
                    "finding": f.finding,
                    "exposure": float(f.financial_impact)
                    if f.financial_impact is not None
                    else None,
                    "dbs_position": f.risk,
                    "required_action": f.recommendation,
                    "dbs_policy_rule": f.dbs_policy_rule,
                }
            )

        counts: dict[str, int] = {}
        for f in findings:
            counts[str(f.severity)] = counts.get(str(f.severity), 0) + 1

        approval_rule_ids = {r.id for r in get_playbook().approval_required()}

        return {
            "document_id": str(document_id),
            "total": len(rows),
            "severity_counts": counts,
            "management_approval_rule_ids": sorted(
                {r["dbs_policy_rule"] for r in rows if r["dbs_policy_rule"] in approval_rule_ids}
            ),
            "rows": rows,
        }
