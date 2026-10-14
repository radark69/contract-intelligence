"""Risk analysis orchestration: playbook matching + fact rules -> Findings.

Idempotent: re-running analysis replaces the document's findings.
Every finding links to evidence (clause or fact source reference).
"""

import logging
from uuid import UUID

from sqlalchemy import delete, select

from app.cross_clause.rules import CrossClauseFinding, run_cross_clause_rules
from app.economics.service import economics_service
from app.playbook.loader import get_playbook
from app.risk_engine.fact_rules import FactRuleContext, FactRuleResult, run_fact_rules
from app.risk_engine.matcher import (
    PLAYBOOK_CATEGORY_TO_FINDING,
    ClauseMatch,
    clause_source_reference,
    match_clauses_against_rules,
)
from app.storage.database import async_session_maker
from app.storage.models import Clause, ContractFact, Finding

logger = logging.getLogger(__name__)


def _match_to_fields(m: ClauseMatch) -> dict:
    position_text = m.rule.reject if m.position == "reject" else m.rule.escalate
    action = (
        "Reject this position; red-line before signature."
        if m.position == "reject"
        else "Escalate for review; negotiate per playbook."
    )
    return {
        "document_id": m.clause.document_id,
        "clause_id": m.clause.id,
        "category": PLAYBOOK_CATEGORY_TO_FINDING.get(
            m.rule.category, PLAYBOOK_CATEGORY_TO_FINDING["commercial"]
        ),
        "severity": m.severity,
        "confidence": m.confidence,
        "finding": f"{m.rule.topic.replace('_', ' ').title()} — {m.position} position ({m.rule.id})",
        "risk": position_text,
        "impact": m.rule.rationale,
        "recommendation": action,
        "dbs_policy_rule": m.rule.id,
        "source_reference": clause_source_reference(m.clause),
        "source_text": m.matched_text,
        "risk_explanation": f"Playbook rule {m.rule.id} matched clause text at {m.position} position.",
        "financial_impact": None,
    }


def _fact_result_to_fields(r: FactRuleResult, document_id: UUID) -> dict:
    return {
        "document_id": document_id,
        "clause_id": r.clause_id,
        "category": r.category,
        "severity": r.severity,
        "confidence": r.confidence,
        "finding": r.finding,
        "risk": r.risk,
        "impact": r.impact,
        "recommendation": r.recommendation,
        "dbs_policy_rule": r.rule_id,
        "source_reference": r.source_reference,
        "source_text": r.source_text,
        "risk_explanation": r.impact,
        "financial_impact": r.financial_impact,
    }


def _cross_to_fields(cf: CrossClauseFinding) -> dict:
    secondary = f" (interacts with {', '.join(cf.secondary_refs)})" if cf.secondary_refs else ""
    return {
        "document_id": cf.primary_clause.document_id,
        "clause_id": cf.primary_clause.id,
        "category": cf.category,
        "severity": cf.severity,
        "confidence": cf.confidence,
        "finding": f"{cf.title} ({cf.rule_id})",
        "risk": cf.risk,
        "impact": cf.conflict,
        "recommendation": cf.recommendation,
        "dbs_policy_rule": cf.rule_id,
        "source_reference": f"{_clause_ref(cf.primary_clause)}{secondary}",
        "source_text": cf.source_text,
        "risk_explanation": cf.conflict,
        "financial_impact": None,
    }


def _clause_ref(clause: Clause) -> str:
    if clause.source_page is not None:
        return f"Page {clause.source_page} → Clause {clause.clause_number or '?'}"
    return f"Clause {clause.clause_number or '?'}"


class RiskEngineService:
    async def analyze_document(self, document_id: UUID) -> list[Finding]:
        playbook = get_playbook()
        async with async_session_maker() as session:
            clauses = list(
                (
                    await session.execute(
                        select(Clause)
                        .where(Clause.document_id == document_id)
                        .order_by(Clause.clause_number)
                    )
                )
                .scalars()
                .all()
            )
            fact_rows = list(
                (
                    await session.execute(
                        select(ContractFact).where(ContractFact.document_id == document_id)
                    )
                )
                .scalars()
                .all()
            )
            facts = {f.key: f for f in fact_rows}

            # Idempotency: replace prior findings for this document.
            await session.execute(delete(Finding).where(Finding.document_id == document_id))

            matches = match_clauses_against_rules(playbook.rules, clauses)
            cross_findings = run_cross_clause_rules(clauses)
            ctx = FactRuleContext(
                facts=facts,
                clauses=clauses,
                rules={r.id: r for r in playbook.rules},
            )
            fact_results = run_fact_rules(ctx)

            # One finding per rule unless it comes from distinct clause matches:
            # clause-linked evidence outranks fact-level duplicates for the same rule.
            matched_rule_ids = {m.rule.id for m in matches}
            fact_results = [
                r
                for r in fact_results
                if r.rule_id == "MISSING-INFO" or r.rule_id not in matched_rule_ids
            ]

            rows = [_match_to_fields(m) for m in matches]
            rows += [_fact_result_to_fields(r, document_id) for r in fact_results]
            rows += [_cross_to_fields(cf) for cf in cross_findings]

            findings = [Finding(**row) for row in rows]
            session.add_all(findings)
            await session.commit()
            for f in findings:
                await session.refresh(f)

            logger.info(
                "risk analysis for %s: %d clause matches, %d fact/gap findings, "
                "%d cross-clause findings",
                document_id,
                len(matches),
                len(fact_results),
                len(cross_findings),
            )

        exposures, notes = await economics_service.calculate_for_document(document_id)
        logger.info(
            "economics for %s: %d exposures, %d cannot-calculate notes",
            document_id,
            len(exposures),
            len(notes),
        )
        return findings


risk_engine_service = RiskEngineService()
