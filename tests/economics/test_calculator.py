from uuid import uuid4

import pytest

from app.economics.calculator import calculate_economics
from app.storage.models import ContractFact


def fact(key: str, value, ref: str = "Page 1") -> ContractFact:
    return ContractFact(
        id=uuid4(),
        document_id=uuid4(),
        key=key,
        label=key,
        value=value,
        raw_value=str(value),
        confidence=0.9,
        source_reference=ref,
        source_text="evidence",
    )


def facts(*fs: ContractFact) -> dict[str, ContractFact]:
    return {f.key: f for f in fs}


FULL = facts(
    fact("contract_value", {"amount": 20_000_000.0, "currency": "USD"}),
    fact("payment_terms_days", 75),
    fact("day_rate", {"amount": 25_000.0, "currency": "USD"}),
    fact("duration", {"months": 36}),
    fact("ld_rate", {"amount": 10_000.0, "currency": "USD", "per": "day"}),
    fact("liability_cap", {"amount": 5_000_000.0, "currency": "USD"}),
)


class TestRevenue:
    def test_stated_value(self):
        out = calculate_economics(FULL)
        assert any(e.result == 20_000_000.0 for e in out.exposures)
        assert any("stated contract value" in e.formula for e in out.exposures)

    def test_missing_value_note(self):
        out = calculate_economics(facts())
        assert any(
            c.metric == "contract revenue" and "contract value" in c.reason
            for c in out.cannot_calculate
        )

    def test_day_rate_run_rate(self):
        out = calculate_economics(FULL)
        run_rate = next(e for e in out.exposures if e.scenario == "day-rate run-rate")
        expected = 25_000.0 * 36 * 30.44
        assert run_rate.result == pytest.approx(expected)
        assert "30.44" in run_rate.formula or "30.44" in run_rate.assumption

    def test_day_rate_without_duration_note(self):
        out = calculate_economics(facts(fact("day_rate", {"amount": 100.0})))
        assert any(
            c.metric == "day-rate revenue run-rate" and "duration" in c.reason
            for c in out.cannot_calculate
        )


class TestWorkingCapital:
    def test_formula(self):
        out = calculate_economics(FULL)
        wc = next(e for e in out.exposures if e.scenario == "receivables outstanding")
        assert wc.result == 20_000_000.0 * 75 / 365.0
        assert "(75) / 365" in wc.formula

    def test_payment_clause_without_days_note(self):
        out = calculate_economics(
            facts(fact("contract_value", {"amount": 1.0})),
            clause_categories={"payment"},
        )
        assert any(c.metric == "working capital requirement" for c in out.cannot_calculate)


class TestLDExposure:
    def test_worst_case(self):
        out = calculate_economics(FULL)
        ld = next(e for e in out.exposures if e.scenario == "worst case (full-term accrual)")
        expected = 10_000.0 * 36 * 30.44
        assert ld.result == pytest.approx(expected)
        assert "Labelled assumption" in ld.assumption

    def test_ld_rate_without_duration(self):
        out = calculate_economics(facts(fact("ld_rate", {"amount": 100.0, "per": "day"})))
        assert any(
            c.metric == "potential LD exposure" and "duration" in c.reason
            for c in out.cannot_calculate
        )

    def test_ld_clause_without_rate(self):
        out = calculate_economics(
            facts(),
            clause_categories={"liquidated_damages"},
        )
        assert any(
            c.metric == "potential LD exposure" and "LD rate" in c.reason
            for c in out.cannot_calculate
        )

    def test_no_ld_evidence_no_note(self):
        out = calculate_economics(facts())
        assert not any(c.metric == "potential LD exposure" for c in out.cannot_calculate)


class TestCashGap:
    def test_labelled_assumption(self):
        out = calculate_economics(FULL)
        gap = next(e for e in out.exposures if e.scenario == "cost-to-cash timing gap")
        assert gap.result == (75 - 30) * 20_000_000.0 / 365.0
        assert "Labelled assumption" in gap.assumption
        assert "net 30" in gap.assumption

    def test_no_negative_gap(self):
        short = facts(
            fact("contract_value", {"amount": 100.0, "currency": "USD"}),
            fact("payment_terms_days", 10),
            fact("duration", {"months": 12}),
        )
        out = calculate_economics(short)
        gap = next(e for e in out.exposures if e.scenario == "cost-to-cash timing gap")
        assert gap.result == 0.0


class TestMarginAndGatedNotes:
    def test_margin_always_needs_cost(self):
        out = calculate_economics(FULL)
        assert any(
            c.metric == "gross contribution and margin" and "direct cost" in c.reason
            for c in out.cannot_calculate
        )

    def test_termination_note_gated_by_clause(self):
        out = calculate_economics(facts(), clause_categories={"termination"})
        assert any(c.metric == "termination exposure" for c in out.cannot_calculate)

    def test_termination_note_absent_without_clause(self):
        out = calculate_economics(FULL)
        assert not any(c.metric == "termination exposure" for c in out.cannot_calculate)

    def test_insurance_gated(self):
        out = calculate_economics(facts(), clause_categories={"insurance"})
        assert any(c.metric == "insurance cost exposure" for c in out.cannot_calculate)


class TestCurrencyAndEvidence:
    def test_currency_from_value_fact(self):
        out = calculate_economics(FULL)
        assert all(e.currency == "USD" for e in out.exposures)

    def test_unspecified_currency(self):
        bare = facts(fact("payment_terms_days", 30))
        # revenue missing; no monetary exposure rows to check — verify helper
        from app.economics.calculator import _currency

        assert _currency(bare) == "UNSPECIFIED"

    def test_every_exposure_has_formula_and_source(self):
        out = calculate_economics(FULL)
        assert out.exposures
        for e in out.exposures:
            assert e.formula
            assert e.source_reference
            assert e.assumption
            assert e.currency
