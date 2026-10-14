from uuid import uuid4

from app.playbook.loader import load_playbook
from app.risk_engine.fact_rules import (
    FactRuleContext,
    check_availability,
    check_liability_cap_vs_value,
    check_missing_ld_rate,
    check_payment_terms,
    run_fact_rules,
)
from app.storage.models import Clause, ContractFact, FindingSeverity


def fact(key: str, value, source_ref: str = "Page 1") -> ContractFact:
    return ContractFact(
        id=uuid4(),
        document_id=uuid4(),
        key=key,
        label=key,
        value=value,
        raw_value=str(value),
        confidence=0.9,
        source_reference=source_ref,
        source_text=f"evidence for {key}",
    )


def clause(category: str, text: str = "text") -> Clause:
    return Clause(
        id=uuid4(),
        document_id=uuid4(),
        raw_text=text,
        category=category,
        source_page=1,
        clause_number="1",
    )


def ctx(facts: list[ContractFact], clauses: list[Clause] | None = None) -> FactRuleContext:
    return FactRuleContext(
        facts={f.key: f for f in facts},
        clauses=clauses or [],
        rules={r.id: r for r in load_playbook().rules},
    )


class TestPaymentTerms:
    def test_seventy_five_days_escalates(self):
        results = check_payment_terms(ctx([fact("payment_terms_days", 75)]))
        assert len(results) == 1
        r = results[0]
        assert r.rule_id == "PAYMENT-001"
        assert r.severity == FindingSeverity.LOW  # medium stepped down
        assert "75" in r.finding

    def test_hundred_days_rejects(self):
        results = check_payment_terms(ctx([fact("payment_terms_days", 100)]))
        r = results[0]
        assert r.severity == FindingSeverity.MEDIUM  # rule severity, reject position
        assert "breach" in r.finding

    def test_sixty_days_ok(self):
        assert check_payment_terms(ctx([fact("payment_terms_days", 60)])) == []

    def test_no_fact_ok(self):
        assert check_payment_terms(ctx([])) == []


class TestAvailability:
    def test_100_percent_is_critical(self):
        results = check_availability(ctx([fact("availability_target", 100)]))
        r = results[0]
        assert r.severity == FindingSeverity.CRITICAL
        assert r.rule_id == "AVAILABILITY-001"

    def test_ninety_nine_escalates(self):
        results = check_availability(ctx([fact("availability_target", 99)]))
        assert results[0].severity == FindingSeverity.HIGH  # critical stepped down

    def test_ninety_five_ok(self):
        assert check_availability(ctx([fact("availability_target", 95)])) == []


class TestRetentionAndNotice:
    def test_retention_over_10(self):
        from app.risk_engine.fact_rules import check_retention

        results = check_retention(ctx([fact("retention_pct", 15)]))
        assert results[0].rule_id == "PAYMENT-004"
        assert results[0].severity == FindingSeverity.LOW

    def test_retention_10_ok(self):
        from app.risk_engine.fact_rules import check_retention

        assert check_retention(ctx([fact("retention_pct", 10)])) == []

    def test_notice_under_30(self):
        from app.risk_engine.fact_rules import check_termination_notice

        results = check_termination_notice(ctx([fact("termination_notice_days", 14)]))
        assert results[0].rule_id == "TERMINATION-003"

    def test_notice_30_ok(self):
        from app.risk_engine.fact_rules import check_termination_notice

        assert check_termination_notice(ctx([fact("termination_notice_days", 30)])) == []


class TestLiabilityCapVsValue:
    def test_cap_over_2x_is_reject(self):
        results = check_liability_cap_vs_value(
            ctx(
                [
                    fact("liability_cap", {"amount": 30_000_000, "currency": "USD"}),
                    fact("contract_value", {"amount": 10_000_000, "currency": "USD"}),
                ]
            )
        )
        r = results[0]
        assert r.severity == FindingSeverity.HIGH  # reject = rule severity
        assert r.financial_impact == 20_000_000

    def test_cap_1_75x_escalates(self):
        results = check_liability_cap_vs_value(
            ctx(
                [
                    fact("liability_cap", {"amount": 17_500_000, "currency": "USD"}),
                    fact("contract_value", {"amount": 10_000_000, "currency": "USD"}),
                ]
            )
        )
        assert results[0].severity == FindingSeverity.MEDIUM  # high stepped down

    def test_cap_under_1_5x_ok(self):
        results = check_liability_cap_vs_value(
            ctx(
                [
                    fact("liability_cap", {"amount": 10_000_000, "currency": "USD"}),
                    fact("contract_value", {"amount": 10_000_000, "currency": "USD"}),
                ]
            )
        )
        assert results == []

    def test_missing_value_no_finding(self):
        results = check_liability_cap_vs_value(ctx([fact("liability_cap", {"amount": 5_000_000})]))
        assert results == []


class TestMissingDetection:
    def test_missing_contract_value_flagged(self):
        results = run_fact_rules(ctx([]))
        keys = [r.dedup_key for r in results]
        assert "missing:contract_value" in keys
        gap = next(r for r in results if r.dedup_key == "missing:contract_value")
        assert gap.severity == FindingSeverity.HIGH
        assert gap.source_reference.startswith("Missing information")

    def test_present_contract_value_not_flagged(self):
        results = run_fact_rules(ctx([fact("contract_value", {"amount": 1, "currency": "USD"})]))
        keys = [r.dedup_key for r in results]
        assert "missing:contract_value" not in keys

    def test_ld_clause_without_rate_flagged(self):
        results = check_missing_ld_rate(
            ctx([], [clause("liquidated_damages", "LDs apply per day")])
        )
        assert results[0].rule_id == "LIQUIDATED_DAMAGES-001"
        assert "Cannot calculate reliably" in results[0].risk

    def test_ld_clause_with_rate_ok(self):
        results = check_missing_ld_rate(
            ctx(
                [fact("ld_rate", {"amount": 100, "per": "day"})],
                [clause("liquidated_damages")],
            )
        )
        assert results == []

    def test_no_ld_clause_no_gap(self):
        assert check_missing_ld_rate(ctx([])) == []

    def test_multiyear_without_escalation_flagged(self):
        from app.risk_engine.fact_rules import check_missing_escalation

        results = check_missing_escalation(
            ctx([fact("duration", {"months": 36})], [clause("pricing")])
        )
        assert results[0].rule_id == "PRICING-002"

    def test_escalation_present_ok(self):
        from app.risk_engine.fact_rules import check_missing_escalation

        results = check_missing_escalation(
            ctx(
                [fact("duration", {"months": 36}), fact("escalation_pct", 5)],
                [clause("pricing")],
            )
        )
        assert results == []


class TestRunFactRules:
    def test_dedupes_by_key(self):
        results = run_fact_rules(
            ctx([fact("payment_terms_days", 75), fact("payment_terms_days", 75)])
        )
        # dict keyed by key means duplicate keys impossible; dedup still holds for gaps
        keys = [r.dedup_key for r in results]
        assert len(keys) == len(set(keys))

    def test_all_results_have_evidence(self):
        results = run_fact_rules(ctx([fact("payment_terms_days", 75)]))
        for r in results:
            assert r.source_reference
            assert r.source_text

    def test_threshold_results_link_rule_text(self):
        results = run_fact_rules(ctx([fact("payment_terms_days", 75)]))
        r = next(x for x in results if x.rule_id == "PAYMENT-001")
        playbook = load_playbook().get("PAYMENT-001")
        assert r.risk == playbook.escalate
