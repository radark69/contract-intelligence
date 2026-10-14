"""Deterministic playbook matching: clause text against rule patterns.

Positions map to severity deterministically (plan: severity must be
supported by explicit criteria, never invented):
  REJECT   -> rule's severity
  ESCALATE -> one severity step below the rule's severity

Every emitted finding carries clause id + source reference + source text
(evidence-first, plan section 9).
"""

import re
from dataclasses import dataclass

from app.playbook.schema import PlaybookRule
from app.storage.models import Clause, FindingCategory, FindingSeverity

SEVERITY_ORDER = [
    FindingSeverity.CRITICAL,
    FindingSeverity.HIGH,
    FindingSeverity.MEDIUM,
    FindingSeverity.LOW,
    FindingSeverity.INFORMATIONAL,
]

PLAYBOOK_CATEGORY_TO_FINDING: dict[str, FindingCategory] = {
    "liability": FindingCategory.LEGAL,
    "indemnity": FindingCategory.LEGAL,
    "termination": FindingCategory.LEGAL,
    "suspension": FindingCategory.LEGAL,
    "dispute_resolution": FindingCategory.LEGAL,
    "force_majeure": FindingCategory.LEGAL,
    "confidentiality": FindingCategory.DATA,
    "commercial": FindingCategory.COMMERCIAL,
    "pricing": FindingCategory.COMMERCIAL,
    "payment": FindingCategory.COMMERCIAL,
    "procurement": FindingCategory.COMMERCIAL,
    "taxes": FindingCategory.FINANCIAL,
    "insurance": FindingCategory.FINANCIAL,
    "liquidated_damages": FindingCategory.FINANCIAL,
    "availability": FindingCategory.OPERATIONAL,
    "operations": FindingCategory.OPERATIONAL,
    "personnel": FindingCategory.OPERATIONAL,
    "hse": FindingCategory.HSE,
    "regulatory": FindingCategory.REGULATORY,
    "nigerian_content": FindingCategory.REGULATORY,
    "scope": FindingCategory.SCOPE,
}


def step_down(severity: FindingSeverity) -> FindingSeverity:
    idx = SEVERITY_ORDER.index(severity)
    return SEVERITY_ORDER[min(idx + 1, len(SEVERITY_ORDER) - 1)]


@dataclass
class ClauseMatch:
    rule: PlaybookRule
    clause: Clause
    position: str  # "reject" | "escalate"
    severity: FindingSeverity
    confidence: float
    matched_text: str


def _find_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            return text[start:end].strip()
    return None


def match_clauses_against_rules(
    rules: list[PlaybookRule], clauses: list[Clause]
) -> list[ClauseMatch]:
    """Match playbook rules against clauses in their target categories.

    Reject positions win over escalate for the same (rule, clause) pair.
    At most one finding per (rule, clause).
    """
    results: list[ClauseMatch] = []
    for rule in rules:
        for clause in clauses:
            if clause.category not in rule.clause_categories:
                continue
            text = clause.raw_text or ""

            matched = _find_match(text, rule.reject_patterns)
            if matched is not None:
                results.append(
                    ClauseMatch(
                        rule=rule,
                        clause=clause,
                        position="reject",
                        severity=rule.severity,
                        confidence=0.95,
                        matched_text=matched,
                    )
                )
                continue

            matched = _find_match(text, rule.escalate_patterns)
            if matched is not None:
                results.append(
                    ClauseMatch(
                        rule=rule,
                        clause=clause,
                        position="escalate",
                        severity=step_down(rule.severity),
                        confidence=0.85,
                        matched_text=matched,
                    )
                )
    return results


def clause_source_reference(clause: Clause) -> str:
    if clause.source_page is not None:
        return f"Page {clause.source_page} → Clause {clause.clause_number or clause.title or '?'}"
    if clause.source_sheet:
        rng = clause.source_range or ""
        return f"Sheet: {clause.source_sheet}" + (f" Range: {rng}" if rng else "")
    return "Clause (no page reference)"
