"""Assemble all review data into a single structure for report rendering."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from app.playbook.loader import get_playbook
from app.risk_engine.matcher import SEVERITY_ORDER
from app.storage.database import async_session_maker
from app.storage.models import (
    Clause,
    ContractFact,
    Document,
    EconomicExposure,
    Finding,
    Obligation,
)


@dataclass
class RegisterRow:
    display_id: str
    severity: str
    category: str
    clause: str
    finding: str
    exposure: float | None
    dbs_position: str
    required_action: str
    rule: str | None
    source_text: str
    impact: str | None
    confidence: float


@dataclass
class ReviewData:
    document: Document
    facts: dict[str, ContractFact]
    findings_sorted: list[Finding]
    register: list[RegisterRow]
    exposures: list[EconomicExposure]
    obligations: list[Obligation]
    cannot_calculate: list[dict]
    severity_counts: dict[str, int]
    approval_rules: list[str]
    clause_count: int


def _display_id(f: Finding, idx: int) -> str:
    if f.dbs_policy_rule == "MISSING-INFO":
        return f"MI-{idx:03d}"
    if f.dbs_policy_rule and f.dbs_policy_rule.startswith("XC-"):
        return f"XC-{idx:03d}"
    return f"CR-{idx:03d}"


async def load_review_data(document_id: UUID) -> ReviewData:
    async with async_session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise ValueError(f"document not found: {document_id}")

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
        findings = list(
            (await session.execute(select(Finding).where(Finding.document_id == document_id)))
            .scalars()
            .all()
        )
        exposures = list(
            (
                await session.execute(
                    select(EconomicExposure).where(EconomicExposure.document_id == document_id)
                )
            )
            .scalars()
            .all()
        )
        obligations = list(
            (await session.execute(select(Obligation).where(Obligation.document_id == document_id)))
            .scalars()
            .all()
        )
        clause_count = len(
            (await session.execute(select(Clause.id).where(Clause.document_id == document_id)))
            .scalars()
            .all()
        )

    findings.sort(key=lambda f: SEVERITY_ORDER.index(f.severity))
    severity_counts: dict[str, int] = {}
    for f in findings:
        severity_counts[str(f.severity)] = severity_counts.get(str(f.severity), 0) + 1

    playbook = get_playbook()
    approval_ids = {r.id for r in playbook.approval_required()}

    register: list[RegisterRow] = []
    for i, f in enumerate(findings, start=1):
        register.append(
            RegisterRow(
                display_id=_display_id(f, i),
                severity=str(f.severity),
                category=str(f.category),
                clause=f.source_reference,
                finding=f.finding,
                exposure=float(f.financial_impact) if f.financial_impact is not None else None,
                dbs_position=f.risk,
                required_action=f.recommendation,
                rule=f.dbs_policy_rule,
                source_text=f.source_text,
                impact=f.impact,
                confidence=float(f.confidence),
            )
        )

    # Cannot-calculate notes: recompute deterministically from facts/clauses.
    from app.economics.calculator import calculate_economics

    categories = set()
    async with async_session_maker() as s2:
        categories = {
            c.category
            for c in (
                (await s2.execute(select(Clause).where(Clause.document_id == document_id)))
                .scalars()
                .all()
            )
            if c.category
        }
    notes = calculate_economics(facts, categories).cannot_calculate

    return ReviewData(
        document=document,
        facts=facts,
        findings_sorted=findings,
        register=register,
        exposures=exposures,
        obligations=obligations,
        cannot_calculate=[{"metric": c.metric, "reason": c.reason} for c in notes],
        severity_counts=severity_counts,
        approval_rules=sorted({r.rule for r in register if r.rule and r.rule in approval_ids}),
        clause_count=clause_count,
    )
