"""Deterministic cross-clause risk rules (plan section 10).

Each rule detects a documented interaction pattern between clauses:
presence of one obligation combined with absence of a protective
counter-provision. Severity criteria are fixed constants in each rule
(plan: severity supported by explicit criteria, not invented).

Evidence: primary clause reference + the secondary clause reference(s)
that complete the interaction.
"""

import re
from dataclasses import dataclass, field

from app.storage.models import Clause, FindingCategory, FindingSeverity


@dataclass
class CrossClauseFinding:
    rule_id: str
    severity: FindingSeverity
    category: FindingCategory
    title: str
    conflict: str
    risk: str
    recommendation: str
    primary_clause: Clause
    source_text: str
    secondary_refs: list[str] = field(default_factory=list)
    confidence: float = 0.9


def _search(clause: Clause, *patterns: str) -> re.Match | None:
    for p in patterns:
        m = re.search(p, clause.raw_text, re.IGNORECASE)
        if m:
            return m
    return None


def _any_clauses(clauses: list[Clause], pattern: str) -> Clause | None:
    for c in clauses:
        if re.search(pattern, c.raw_text, re.IGNORECASE):
            return c
    return None


def _in_categories(clauses: list[Clause], *cats: str) -> list[Clause]:
    return [c for c in clauses if c.category in cats]


def _excerpt(clause: Clause, m: re.Match | None, radius: int = 60) -> str:
    if m is None:
        return clause.raw_text[: 2 * radius].strip()
    start = max(0, m.start() - radius)
    end = min(len(clause.raw_text), m.end() + radius)
    return clause.raw_text[start:end].strip()


def _ref(clause: Clause) -> str:
    if clause.source_page is not None:
        return f"Page {clause.source_page} → Clause {clause.clause_number or '?'}"
    return f"Clause {clause.clause_number or clause.title or '?'}"


# --- Rule implementations ----------------------------------------------------

UNCAPPED = r"uncapped|unlimited liability|liability (?:shall )?(?:not be|is not) limited"
TFC = r"terminat\w+[^.\n]{0,80}(?:convenience|without cause)|for convenience"
DEEMED = r"deemed (?:to be )?(?:approved|accepted)|automatically approved"
APPROVAL = r"(?:invoice|payment)[^.\n]{0,60}approv|approv[^.\n]{0,60}(?:invoice|payment)"
EXCLUSION = r"exclud|except|does not apply|pre-existing|latent defect|force majeure"
MOB_RECOVERY = r"(?:mobilis\w+|demobilis\w+)[^.\n]{0,100}(?:recover|reimburs|pay|refund)|(?:recover|reimburs|refund)[^.\n]{0,100}(?:mobilis\w+|demobilis\w+)|on (?:any )?terminat[^.\n]{0,120}(?:cost|compensat)"
BROAD_SCOPE = (
    r"\bany (?:and all|work|service|activit)\b|whatever (?:is |)requir|all work(?:s)? and services"
)
FIXED_PRICE = r"fixed (?:price|rate)|lump[- ]sum"
VARIATION_ADJ = r"(?:price|rate|fee)[^.\n]{0,40}(?:adjust|equitable variation)|variation[^.\n]{0,60}(?:rate|price)"
CLIENT_EQUIP = r"client[- ]supplied|client'?s (?:equipment|property|asset)|owner[- ]supplied|company[- ]supplied"
CONTRACTOR_GUARANTEE = r"contractor[^.\n]{0,60}(?:guarantee|warrant|ensure|liable)[^.\n]{0,80}equipment|guarantee[^.\n]{0,60}(?:performance|operation)[^.\n]{0,40}equipment"
DEFINED = r"\bmeans\b|is defined as|(?:term|word)s? (?:used )?in this"
DOWNTIME_DEF = r"(?:downtime|non[- ]productive time|npt)[^.\n]{0,80}\bmeans\b|means[^.\n]{0,60}(?:downtime|npt)"
AVAILABILITY_DEF = r"availability[^.\n]{0,80}\bmeans\b|means[^.\n]{0,60}availability"
BROAD_DOWNTIME = r"(?:all|any) (?:downtime|npt|non[- ]productive)[^.\n]{0,60}(?:contractor|service provider)|contractor[^.\n]{0,60}(?:all|any) (?:downtime|npt)"


def check_ld_with_uncapped(clauses: list[Clause]) -> list[CrossClauseFinding]:
    ld = _in_categories(clauses, "liquidated_damages")
    if not ld:
        return []
    liability = _in_categories(clauses, "liability")
    for lc in liability:
        m = _search(lc, UNCAPPED)
        if m:
            return [
                CrossClauseFinding(
                    rule_id="XC-LD-UNCAPPED",
                    severity=FindingSeverity.CRITICAL,  # criterion: duplicate uncapped exposure
                    category=FindingCategory.FINANCIAL,
                    title="Liquidated damages stack with uncapped liability",
                    conflict="LD clause plus uncapped liability for the same breach creates duplicate, unlimited exposure.",
                    risk="The same delay or performance failure can be charged as LDs and again as uncapped damages.",
                    recommendation="Make LDs the exclusive remedy inside a defined liability cap before signature.",
                    primary_clause=ld[0],
                    source_text=_excerpt(ld[0], _search(ld[0], r"liquidated|delay")),
                    secondary_refs=[_ref(lc)],
                )
            ]
    return []


def check_availability_broad_downtime(clauses: list[Clause]) -> list[CrossClauseFinding]:
    avail = _in_categories(clauses, "availability", "downtime_npt")
    if not avail:
        return []
    for c in avail:
        if _search(c, BROAD_DOWNTIME) and not _search(c, EXCLUSION):
            return [
                CrossClauseFinding(
                    rule_id="XC-AVAIL-DOWNTIME",
                    severity=FindingSeverity.HIGH,  # criterion: guarantee + no exclusions
                    category=FindingCategory.OPERATIONAL,
                    title="Availability guarantee combined with broad downtime responsibility",
                    conflict="Availability is guaranteed while all downtime is assigned to DBS without exclusions.",
                    risk="Client delay, force majeure and pre-existing defects count against the guarantee.",
                    recommendation="Add defined exclusion categories and reconcile the downtime definition with the guarantee.",
                    primary_clause=c,
                    source_text=_excerpt(c, _search(c, BROAD_DOWNTIME)),
                )
            ]
    return []


def check_approval_without_deemed(clauses: list[Clause]) -> list[CrossClauseFinding]:
    payment = _in_categories(clauses, "payment")
    if not payment or _any_clauses(clauses, DEEMED):
        return []
    for c in payment:
        m = _search(c, APPROVAL)
        if m:
            return [
                CrossClauseFinding(
                    rule_id="XC-APPROVAL-NODEEM",
                    severity=FindingSeverity.HIGH,  # criterion: payment can stall indefinitely
                    category=FindingCategory.COMMERCIAL,
                    title="Client invoice approval without deemed-approval deadline",
                    conflict="Invoices require client approval but no clause deems them approved after a deadline.",
                    risk="Payment can stall indefinitely while work continues.",
                    recommendation="Add deemed approval within 10–15 business days of submission.",
                    primary_clause=c,
                    source_text=_excerpt(c, m),
                )
            ]
    return []


def check_termination_without_mob_recovery(clauses: list[Clause]) -> list[CrossClauseFinding]:
    term = _in_categories(clauses, "termination")
    if not term:
        return []
    for c in term:
        m = _search(c, TFC)
        if not m:
            continue
        if _any_clauses(clauses, MOB_RECOVERY):
            return []
        return [
            CrossClauseFinding(
                rule_id="XC-TERM-NOMOB",
                severity=FindingSeverity.HIGH,  # criterion: stranded committed spend
                category=FindingCategory.LEGAL,
                title="Termination for convenience without mobilisation cost recovery",
                conflict="Client may terminate for convenience but no clause recovers mobilisation, demobilisation or stranded costs.",
                risk="Committed mobilisation spend is stranded on termination.",
                recommendation="Require payment of WIP, demobilisation and stranded costs on any termination.",
                primary_clause=c,
                source_text=_excerpt(c, m),
            )
        ]
    return []


def check_broad_scope_fixed_price(clauses: list[Clause]) -> list[CrossClauseFinding]:
    scope = _in_categories(clauses, "scope")
    pricing = _in_categories(clauses, "pricing")
    if not scope or not pricing:
        return []
    if _any_clauses(clauses, VARIATION_ADJ):
        return []
    for sc in scope:
        m1 = _search(sc, BROAD_SCOPE)
        if not m1:
            continue
        for pc in pricing:
            m2 = _search(pc, FIXED_PRICE)
            if m2:
                return [
                    CrossClauseFinding(
                        rule_id="XC-SCOPE-FIXED",
                        severity=FindingSeverity.HIGH,  # criterion: open-ended scope, closed price
                        category=FindingCategory.SCOPE,
                        title="Broad scope combined with fixed pricing",
                        conflict="Scope language covers any/all work while pricing is fixed with no adjustment mechanism.",
                        risk="Unpriced scope growth converts the fixed price into open-ended loss.",
                        recommendation="Add variation pricing or cap the scope definition.",
                        primary_clause=sc,
                        source_text=_excerpt(sc, m1),
                        secondary_refs=[_ref(pc)],
                    )
                ]
    return []


def check_client_equipment_guarantee(clauses: list[Clause]) -> list[CrossClauseFinding]:
    equip = _any_clauses(clauses, CLIENT_EQUIP)
    if equip is None:
        return []
    for c in clauses:
        if c.id == equip.id:
            continue
        if c.category in ("availability", "kpi", "scope", "maintenance", "indemnity", "liability"):
            m = _search(c, CONTRACTOR_GUARANTEE)
            if m:
                return [
                    CrossClauseFinding(
                        rule_id="XC-CLIENT-EQUIP",
                        severity=FindingSeverity.HIGH,  # criterion: risk over asset outside DBS control
                        category=FindingCategory.OPERATIONAL,
                        title="Performance guarantee over client-supplied equipment",
                        conflict="Client supplies the equipment but DBS guarantees its performance/availability.",
                        risk="DBS is accountable for failures in an asset it does not control.",
                        recommendation="Carve client-supplied equipment out of guarantees or condition them on maintenance access.",
                        primary_clause=c,
                        source_text=_excerpt(c, m),
                        secondary_refs=[_ref(equip)],
                    )
                ]
    return []


def check_maintenance_without_exclusions(clauses: list[Clause]) -> list[CrossClauseFinding]:
    for c in _in_categories(clauses, "maintenance"):
        m = _search(c, r"keep[^.\n]{0,40}(?:order|condition)|maintain (?:in )?(?:good )?work")
        if m and not _search(c, EXCLUSION):
            return [
                CrossClauseFinding(
                    rule_id="XC-MAINT-NOEXCL",
                    severity=FindingSeverity.MEDIUM,  # criterion: covers pre-existing failures
                    category=FindingCategory.OPERATIONAL,
                    title="Maintenance obligation without defined exclusions",
                    conflict="Broad maintenance duty with no exclusions for pre-existing defects or client-caused failure.",
                    risk="DBS becomes liable for conditions it never caused.",
                    recommendation="Add exclusions for pre-existing defects, latent defects and client-caused failure.",
                    primary_clause=c,
                    source_text=_excerpt(c, m),
                )
            ]
    return []


def check_conflicting_definitions(clauses: list[Clause]) -> list[CrossClauseFinding]:
    avail_def = None
    down_def = None
    for c in clauses:
        if (
            avail_def is None
            and c.category in ("availability", "kpi")
            and _search(c, AVAILABILITY_DEF)
        ):
            avail_def = c
        if (
            down_def is None
            and c.category in ("downtime_npt", "liquidated_damages")
            and _search(c, DOWNTIME_DEF)
        ):
            down_def = c
    if avail_def and down_def and avail_def.id != down_def.id:
        return [
            CrossClauseFinding(
                rule_id="XC-DEFINITION-CONFLICT",
                severity=FindingSeverity.MEDIUM,  # criterion: measurement ambiguity
                category=FindingCategory.OPERATIONAL,
                title="Conflicting downtime / availability definitions",
                conflict="Availability and downtime are defined in separate clauses that may not reconcile.",
                risk="LDs can accrue on hours excluded from the availability calculation.",
                recommendation="Adopt one definition set used by both the guarantee and the LD clause.",
                primary_clause=avail_def,
                source_text=_excerpt(avail_def, _search(avail_def, AVAILABILITY_DEF)),
                secondary_refs=[_ref(down_def)],
                confidence=0.75,
            )
        ]
    return []


ALL_CROSS_RULES = [
    check_ld_with_uncapped,
    check_availability_broad_downtime,
    check_approval_without_deemed,
    check_termination_without_mob_recovery,
    check_broad_scope_fixed_price,
    check_client_equipment_guarantee,
    check_maintenance_without_exclusions,
    check_conflicting_definitions,
]


def run_cross_clause_rules(clauses: list[Clause]) -> list[CrossClauseFinding]:
    findings: list[CrossClauseFinding] = []
    for rule in ALL_CROSS_RULES:
        findings.extend(rule(clauses))
    return findings
