"""Deterministic fact-based risk rules and missing-information detection.

Two families (Sprint 5):
  1. Threshold checks — extracted facts compared against playbook
     thresholds (e.g. payment days > 60, cap > 150% of value).
  2. Missing-information detector — expected facts absent given positive
     evidence the contract needs them (clause present, or universally
     material like contract value).

Every result carries source evidence from the fact that triggered it, or
an explicit document-wide scan reference when the finding is an absence.
"""

from dataclasses import dataclass
from uuid import UUID

from app.playbook.schema import PlaybookRule
from app.risk_engine.matcher import PLAYBOOK_CATEGORY_TO_FINDING, step_down
from app.storage.models import Clause, ContractFact, FindingCategory, FindingSeverity


@dataclass
class FactRuleResult:
    rule_id: str
    category: FindingCategory
    severity: FindingSeverity
    confidence: float
    finding: str
    risk: str
    recommendation: str
    source_reference: str
    source_text: str
    impact: str | None = None
    financial_impact: float | None = None
    clause_id: UUID | None = None
    dedup_key: str = ""


@dataclass
class FactRuleContext:
    facts: dict[str, ContractFact]
    clauses: list[Clause]
    rules: dict[str, PlaybookRule]

    @property
    def clause_categories(self) -> set[str]:
        return {c.category for c in self.clauses if c.category}

    def clause_of_category(self, category: str) -> Clause | None:
        for c in self.clauses:
            if c.category == category:
                return c
        return None

    def fact_value(
        self, name: str, field_name: str | None = None
    ) -> dict | list | str | float | bool | None:
        f = self.facts.get(name)
        if f is None or f.value is None:
            return None
        if field_name is None:
            return f.value
        if isinstance(f.value, dict):
            return f.value.get(field_name)
        return None


def _rule(
    ctx: FactRuleContext, rule_id: str, default_category: FindingCategory
) -> tuple[FindingCategory, str]:
    rule = ctx.rules.get(rule_id)
    if rule is None:
        return default_category, rule_id
    return PLAYBOOK_CATEGORY_TO_FINDING.get(rule.category, default_category), rule_id


def _evidence(fact: ContractFact) -> tuple[str, str]:
    return fact.source_reference, fact.source_text


def _amount(ctx: FactRuleContext, key: str) -> float | None:
    v = ctx.fact_value(key, "amount")
    if v is None:
        raw = ctx.fact_value(key)
        v = raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def check_payment_terms(ctx: FactRuleContext) -> list[FactRuleResult]:
    out: list[FactRuleResult] = []
    fact = ctx.facts.get("payment_terms_days")
    if fact is None or not isinstance(fact.value, (int, float)):
        return out
    days = float(fact.value)
    category, rule_id = _rule(ctx, "PAYMENT-001", FindingCategory.COMMERCIAL)
    if days > 90:
        out.append(
            FactRuleResult(
                rule_id=rule_id,
                category=category,
                severity=ctx.rules[rule_id].severity
                if rule_id in ctx.rules
                else FindingSeverity.MEDIUM,
                confidence=0.93,
                finding=f"Payment terms of {days:.0f} days breach DBS red-line (net 91+ days)",
                risk=ctx.rules[rule_id].reject if rule_id in ctx.rules else "Long payment terms",
                impact="Days payable beyond DBS's acceptable window increase working-capital cost and client credit exposure.",
                recommendation="Negotiate payment terms back to net 60 or better before signature.",
                financial_impact=None,
                **_evidence_fields(fact),
                dedup_key=f"{rule_id}:payment_days",
            )
        )
    elif days > 60:
        step_sev = (
            step_down(ctx.rules[rule_id].severity) if rule_id in ctx.rules else FindingSeverity.LOW
        )
        out.append(
            FactRuleResult(
                rule_id=rule_id,
                category=category,
                severity=step_sev,
                confidence=0.9,
                finding=f"Payment terms of {days:.0f} days exceed the preferred net 60 window",
                risk=ctx.rules[rule_id].escalate
                if rule_id in ctx.rules
                else "Extended payment terms",
                impact="Each extra day beyond 60 increases the working-capital requirement on this contract.",
                recommendation="Escalate for approval or negotiate improved terms.",
                **_evidence_fields(fact),
                dedup_key=f"{rule_id}:payment_days",
            )
        )
    return out


def _evidence_fields(fact: ContractFact) -> dict:
    return {"source_reference": fact.source_reference, "source_text": fact.source_text}


def check_availability(ctx: FactRuleContext) -> list[FactRuleResult]:
    out: list[FactRuleResult] = []
    fact = ctx.facts.get("availability_target")
    if fact is None or not isinstance(fact.value, (int, float)):
        return out
    target = float(fact.value)
    rule = ctx.rules.get("AVAILABILITY-001")
    category = FindingCategory.OPERATIONAL
    if target >= 100:
        out.append(
            FactRuleResult(
                rule_id="AVAILABILITY-001",
                category=category,
                severity=rule.severity if rule else FindingSeverity.CRITICAL,
                confidence=0.95,
                finding=f"{target:.0f}% availability guarantee with no tolerance",
                risk=rule.reject if rule else "100% availability guarantee",
                impact="Any idle hour — including client delay and force majeure — becomes a breach.",
                recommendation="Reject; negotiate target with defined exclusions and measurement window.",
                financial_impact=None,
                **_evidence_fields(fact),
                dedup_key="AVAILABILITY-001:target_100",
            )
        )
    elif target > 98:
        sev = step_down(rule.severity) if rule else FindingSeverity.HIGH
        out.append(
            FactRuleResult(
                rule_id="AVAILABILITY-001",
                category=category,
                severity=sev,
                confidence=0.9,
                finding=f"Availability target of {target:.1f}% is above the 98% escalation threshold",
                risk=rule.escalate if rule else "Availability above escalation threshold",
                impact="High guaranteed availability narrows the exclusion window for NPT and client delay.",
                recommendation="Escalate; confirm exclusions are defined and measurable.",
                **_evidence_fields(fact),
                dedup_key="AVAILABILITY-001:target_high",
            )
        )
    return out


def check_retention(ctx: FactRuleContext) -> list[FactRuleResult]:
    out: list[FactRuleResult] = []
    fact = ctx.facts.get("retention_pct")
    if fact is None or not isinstance(fact.value, (int, float)):
        return out
    pct = float(fact.value)
    if pct <= 10:
        return out
    rule = ctx.rules.get("PAYMENT-004")
    sev = step_down(rule.severity) if rule else FindingSeverity.LOW
    out.append(
        FactRuleResult(
            rule_id="PAYMENT-004",
            category=FindingCategory.COMMERCIAL,
            severity=sev,
            confidence=0.9,
            finding=f"Retention of {pct:.0f}% exceeds the 10% acceptable ceiling",
            risk=rule.escalate if rule else "Retention above acceptable ceiling",
            impact="Retention held beyond the ceiling is unreturned working capital until release.",
            recommendation="Negotiate retention to ≤10% with a hard release deadline.",
            **_evidence_fields(fact),
            dedup_key="PAYMENT-004:retention_pct",
        )
    )
    return out


def check_termination_notice(ctx: FactRuleContext) -> list[FactRuleResult]:
    out: list[FactRuleResult] = []
    fact = ctx.facts.get("termination_notice_days")
    if fact is None or not isinstance(fact.value, (int, float)):
        return out
    days = float(fact.value)
    if days >= 30:
        return out
    rule = ctx.rules.get("TERMINATION-003")
    sev = step_down(rule.severity) if rule else FindingSeverity.LOW
    out.append(
        FactRuleResult(
            rule_id="TERMINATION-003",
            category=FindingCategory.LEGAL,
            severity=sev,
            confidence=0.9,
            finding=f"Termination notice of {days:.0f} days is below the 30-day threshold",
            risk=rule.escalate if rule else "Short termination notice",
            impact="Short notice prevents orderly demobilisation and increases stranded-cost exposure.",
            recommendation="Negotiate ≥30 days notice (target 90).",
            **_evidence_fields(fact),
            dedup_key="TERMINATION-003:notice_days",
        )
    )
    return out


def check_liability_cap_vs_value(ctx: FactRuleContext) -> list[FactRuleResult]:
    out: list[FactRuleResult] = []
    cap = _amount(ctx, "liability_cap")
    value = _amount(ctx, "contract_value")
    if cap is None or value is None or value <= 0:
        return out
    ratio = cap / value
    rule = ctx.rules.get("LIABILITY-004")
    cap_fact = ctx.facts["liability_cap"]
    if ratio > 2.0:
        out.append(
            FactRuleResult(
                rule_id="LIABILITY-004",
                category=FindingCategory.LEGAL,
                severity=rule.severity if rule else FindingSeverity.HIGH,
                confidence=0.9,
                finding=f"Liability cap is {ratio:.2f}× contract value (red-line: >2×)",
                risk=rule.reject if rule else "Cap above 200% of contract value",
                impact=f"Cap of {cap:,.0f} against contract value of {value:,.0f} exceeds board-approval territory.",
                recommendation="Reject; obtain management approval or renegotiate the cap.",
                financial_impact=cap - value,
                **_evidence_fields(cap_fact),
                dedup_key="LIABILITY-004:cap_ratio",
            )
        )
    elif ratio > 1.5:
        sev = step_down(rule.severity) if rule else FindingSeverity.MEDIUM
        out.append(
            FactRuleResult(
                rule_id="LIABILITY-004",
                category=FindingCategory.LEGAL,
                severity=sev,
                confidence=0.9,
                finding=f"Liability cap is {ratio:.2f}× contract value (threshold: 1.5×)",
                risk=rule.escalate if rule else "Cap above 150% of contract value",
                impact=f"Cap of {cap:,.0f} is materially above contract value of {value:,.0f}.",
                recommendation="Escalate for management approval.",
                financial_impact=cap - value,
                **_evidence_fields(cap_fact),
                dedup_key="LIABILITY-004:cap_ratio",
            )
        )
    return out


def check_missing_escalation(ctx: FactRuleContext) -> list[FactRuleResult]:
    if "pricing" not in ctx.clause_categories:
        return []
    if ctx.facts.get("escalation_pct") is not None:
        return []
    duration = ctx.fact_value("duration", "months")
    if not isinstance(duration, (int, float)) or duration < 12:
        return []
    rule = ctx.rules.get("PRICING-002")
    clause = ctx.clause_of_category("pricing")
    ref = "Missing information — pricing clauses scanned"
    text = f"No escalation mechanism found in pricing clauses; term is {duration:.0f} months."
    return [
        FactRuleResult(
            rule_id="PRICING-002",
            category=FindingCategory.COMMERCIAL,
            severity=step_down(rule.severity) if rule else FindingSeverity.LOW,
            confidence=0.8,
            finding=f"Multi-year term ({duration:.0f} months) with no escalation mechanism found",
            risk=rule.escalate if rule else "No escalation on multi-year contract",
            impact="Fixed pricing across a multi-year term transfers all inflation risk to DBS.",
            recommendation="Negotiate an annual escalation mechanism or index-linked adjustment.",
            source_reference=ref,
            source_text=text,
            clause_id=clause.id if clause else None,
            dedup_key="PRICING-002:no_escalation",
        )
    ]


def check_missing_ld_rate(ctx: FactRuleContext) -> list[FactRuleResult]:
    if "liquidated_damages" not in ctx.clause_categories:
        return []
    if ctx.facts.get("ld_rate") is not None:
        return []
    rule = ctx.rules.get("LIQUIDATED_DAMAGES-001")
    clause = ctx.clause_of_category("liquidated_damages")
    return [
        FactRuleResult(
            rule_id="LIQUIDATED_DAMAGES-001",
            category=FindingCategory.FINANCIAL,
            severity=step_down(rule.severity) if rule else FindingSeverity.MEDIUM,
            confidence=0.8,
            finding="Liquidated damages clause present but no LD rate found",
            risk="Cannot calculate reliably — missing LD rate / downtime definition.",
            impact="LD exposure cannot be quantified until the rate is stated.",
            recommendation="Request the LD rate schedule; flag in the missing-information register.",
            source_reference="Missing information — LD clauses scanned",
            source_text="LD clauses detected without a matching LD rate value.",
            clause_id=clause.id if clause else None,
            dedup_key="LIQUIDATED_DAMAGES-001:missing_rate",
        )
    ]


# --- Missing-information detector -------------------------------------------


GAP_RULES: list[tuple[str, FindingCategory, FindingSeverity, str, str]] = [
    (
        "contract_value",
        FindingCategory.FINANCIAL,
        FindingSeverity.HIGH,
        "Contract value not found in the document",
        "Without a contract value, exposure, caps and approvals cannot be assessed.",
    ),
    (
        "currency",
        FindingCategory.FINANCIAL,
        FindingSeverity.MEDIUM,
        "Contract currency not identified",
        "Monetary amounts may be assumed in the wrong currency.",
    ),
    (
        "start_date",
        FindingCategory.SCHEDULE,
        FindingSeverity.MEDIUM,
        "Contract start date not found",
        "Term, renewal and notice calculations cannot be verified.",
    ),
    (
        "end_date",
        FindingCategory.SCHEDULE,
        FindingSeverity.MEDIUM,
        "Contract end/expiry date not found",
        "Term, renewal and notice calculations cannot be verified.",
    ),
]


def detect_missing_information(ctx: FactRuleContext) -> list[FactRuleResult]:
    out: list[FactRuleResult] = []
    for key, category, severity, finding, impact in GAP_RULES:
        if key in ctx.facts:
            continue
        out.append(
            FactRuleResult(
                rule_id="MISSING-INFO",
                category=category,
                severity=severity,
                confidence=0.95,
                finding=finding,
                risk="Missing information",
                impact=impact,
                recommendation=f"Request clarification: {finding[0].lower()}{finding[1:]}",
                source_reference="Missing information — document-wide scan",
                source_text=f"No '{key}' value found across extracted pages and sheets.",
                dedup_key=f"missing:{key}",
            )
        )

    if "payment" in ctx.clause_categories and "payment_terms_days" not in ctx.facts:
        clause = ctx.clause_of_category("payment")
        out.append(
            FactRuleResult(
                rule_id="MISSING-INFO",
                category=FindingCategory.COMMERCIAL,
                severity=FindingSeverity.MEDIUM,
                confidence=0.9,
                finding="Payment clauses present but no payment term (days) found",
                risk="Missing information",
                impact="Working-capital exposure cannot be calculated.",
                recommendation="Request the payment term definition.",
                source_reference="Missing information — payment clauses scanned",
                source_text="Payment clauses detected without a numeric payment term.",
                clause_id=clause.id if clause else None,
                dedup_key="missing:payment_terms_days",
            )
        )
    return out


ALL_FACT_CHECKS = [
    check_payment_terms,
    check_availability,
    check_retention,
    check_termination_notice,
    check_liability_cap_vs_value,
    check_missing_escalation,
    check_missing_ld_rate,
]


def run_fact_rules(ctx: FactRuleContext) -> list[FactRuleResult]:
    """Run all threshold checks and the missing-information detector."""
    results: list[FactRuleResult] = []
    for check in ALL_FACT_CHECKS:
        results.extend(check(ctx))
    results.extend(detect_missing_information(ctx))

    seen: set[str] = set()
    deduped: list[FactRuleResult] = []
    for r in results:
        key = r.dedup_key or f"{r.rule_id}:{r.finding}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped
