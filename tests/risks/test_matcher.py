from uuid import uuid4

import pytest

from app.playbook.loader import load_playbook
from app.risk_engine.matcher import (
    clause_source_reference,
    match_clauses_against_rules,
    step_down,
)
from app.storage.models import Clause, FindingSeverity


def make_clause(category: str, text: str, **kwargs) -> Clause:
    return Clause(
        id=uuid4(),
        document_id=uuid4(),
        raw_text=text,
        category=category,
        **kwargs,
    )


@pytest.fixture(scope="module")
def rules():
    return load_playbook().rules


class TestStepDown:
    def test_critical_to_high(self):
        assert step_down(FindingSeverity.CRITICAL) == FindingSeverity.HIGH

    def test_high_to_medium(self):
        assert step_down(FindingSeverity.HIGH) == FindingSeverity.MEDIUM

    def test_informational_floor(self):
        assert step_down(FindingSeverity.INFORMATIONAL) == FindingSeverity.INFORMATIONAL


class TestMatchClauses:
    def test_reject_pattern_detected(self, rules):
        clause = make_clause(
            "liability", "The Contractor shall accept unlimited liability for all claims."
        )
        matches = match_clauses_against_rules(rules, [clause])
        assert len(matches) == 1
        m = matches[0]
        assert m.rule.id == "LIABILITY-001"
        assert m.position == "reject"
        assert m.severity == FindingSeverity.CRITICAL
        assert m.confidence == 0.95
        assert "unlimited liability" in m.matched_text

    def test_reject_wins_over_escalate(self, rules):
        clause = make_clause(
            "liability",
            "Uncapped liability applies. The cap may also exceed agreed thresholds "
            "and the liability shall not be limited in any way.",
        )
        matches = [
            m for m in match_clauses_against_rules(rules, [clause]) if m.rule.id == "LIABILITY-001"
        ]
        assert len(matches) == 1
        assert matches[0].position == "reject"

    def test_escalate_steps_severity_down(self, rules):
        clause = make_clause(
            "payment", "Invoices are payable within 75 days of receipt of invoice."
        )
        matches = match_clauses_against_rules(rules, [clause])
        assert matches
        m = matches[0]
        assert m.position == "escalate"
        # PAYMENT-001 severity is medium -> escalate is low
        assert m.severity == FindingSeverity.LOW
        assert m.confidence == 0.85

    def test_clause_category_filter(self, rules):
        # uncapped text in a clause NOT classified as liability -> no match
        clause = make_clause("confidentiality", "unlimited liability for all claims")
        matches = match_clauses_against_rules(rules, [clause])
        assert matches == []

    def test_one_finding_per_rule_clause(self, rules):
        clause = make_clause(
            "termination",
            "terminate for convenience " * 50 + "without any payment or cost recovery",
        )
        matches = match_clauses_against_rules(rules, [clause])
        ids = [(m.rule.id, m.clause.id) for m in matches]
        assert len(ids) == len(set(ids))

    def test_no_rules_no_matches(self):
        clause = make_clause("liability", "unlimited liability")
        assert match_clauses_against_rules([], [clause]) == []


class TestSourceReference:
    def test_pdf_page(self):
        c = make_clause("liability", "x", source_page=3, clause_number="12.4")
        assert clause_source_reference(c) == "Page 3 → Clause 12.4"

    def test_xlsx_sheet_range(self):
        c = make_clause("payment", "x", source_sheet="Commercial Terms", source_range="B14:F18")
        assert clause_source_reference(c) == "Sheet: Commercial Terms Range: B14:F18"

    def test_sheet_no_range(self):
        c = make_clause("payment", "x", source_sheet="Payment")
        assert clause_source_reference(c) == "Sheet: Payment"

    def test_no_reference(self):
        c = make_clause("payment", "x")
        assert "no page reference" in clause_source_reference(c)
