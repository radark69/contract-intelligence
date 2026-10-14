import re

import pytest

from app.playbook.loader import load_playbook
from app.playbook.schema import PlaybookCategory, PlaybookRule
from app.storage.models import FindingSeverity

VALID = {
    "id": "LIABILITY-099",
    "category": "liability",
    "topic": "test topic",
    "severity": "high",
    "preferred": "p",
    "acceptable": "a",
    "escalate": "e",
    "reject": "r",
    "clause_categories": ["liability"],
}


def rule(**overrides) -> PlaybookRule:
    return PlaybookRule.model_validate({**VALID, **overrides})


@pytest.fixture(scope="module")
def playbook():
    return load_playbook()


class TestSchema:
    def test_valid_rule(self):
        r = rule()
        assert r.severity == FindingSeverity.HIGH
        assert r.category == PlaybookCategory.LIABILITY

    def test_bad_id_format(self):
        with pytest.raises(ValueError):
            rule(id="liability-99")

    def test_id_prefix_must_match_category(self):
        with pytest.raises(ValueError, match="prefix"):
            rule(id="PAYMENT-001")

    def test_invalid_regex_rejected(self):
        with pytest.raises(ValueError, match="invalid regex"):
            rule(reject_patterns=["("])

    def test_unknown_clause_category_rejected(self):
        with pytest.raises(ValueError, match="unknown clause categories"):
            rule(clause_categories=["not_a_category"])

    def test_approval_defaults_false(self):
        assert rule().requires_management_approval is False


class TestShippedRules:
    """Integrity checks over the actual DBS playbook."""

    def test_rule_count_in_plan_range(self, playbook):
        assert 20 <= len(playbook) <= 30

    def test_all_severities_valid(self, playbook):
        for r in playbook.rules:
            assert r.severity in set(FindingSeverity)

    def test_id_prefix_matches_category_everywhere(self, playbook):
        for r in playbook.rules:
            assert r.id.startswith(f"{r.category.upper()}-"), r.id

    def test_every_rule_has_rationale(self, playbook):
        for r in playbook.rules:
            assert len(r.rationale.strip()) > 20, r.id

    def test_every_rule_has_all_four_positions(self, playbook):
        for r in playbook.rules:
            assert r.preferred and r.acceptable and r.escalate and r.reject, r.id

    def test_critical_rules_require_management_approval(self, playbook):
        for r in playbook.rules:
            if r.severity == FindingSeverity.CRITICAL:
                assert r.requires_management_approval, r.id

    def test_patterns_compile(self, playbook):
        for r in playbook.rules:
            for p in r.reject_patterns + r.escalate_patterns:
                re.compile(p, re.IGNORECASE)

    def test_reject_rules_have_reject_patterns(self, playbook):
        reject_or_critical = [
            r
            for r in playbook.rules
            if "uncapped" in r.reject.lower() or r.severity == FindingSeverity.CRITICAL
        ]
        assert reject_or_critical
        for r in reject_or_critical:
            assert r.reject_patterns, r.id

    def test_coverage_of_plan_core_categories(self, playbook):
        categories = {r.category for r in playbook.rules}
        for required in (
            "liability",
            "payment",
            "termination",
            "insurance",
            "liquidated_damages",
            "availability",
            "hse",
            "regulatory",
        ):
            assert required in categories, f"missing playbook category: {required}"
