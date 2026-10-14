from app.facts.extractor import TextSpan, extract_facts


def facts(text: str) -> dict[str, list]:
    found = extract_facts([TextSpan(text=text, source_reference="Page 1")])
    by_key: dict[str, list] = {}
    for f in found:
        by_key.setdefault(f.key, []).append(f)
    return by_key


CONTRACT = """\
CLIENT: Omega Energy Limited
CONTRACTOR: DBS Drilling Services Ltd

1. COMMERCIAL
Contract Value: USD 20,000,000
Payment terms: within 60 days of invoice
Day Rate: USD 25,000
Standby rate: USD 12,500 per day
Annual escalation of 5% per annum
Withholding tax of 10% shall apply
Retention: 10%
Nigerian Content: 45%

2. TERM
This Agreement shall commence on 1 January 2026 and continue for 36 months.
The expiry date is 31 December 2028.

3. OPERATIONS
Contractor guarantees 98% availability of the rigs.

4. LIQUIDATED DAMAGES
Liquidated damages of USD 10,000 per day shall apply for each day of delay.

5. LIABILITY
The liability of the Contractor shall be capped at USD 5,000,000.
The Contractor shall maintain insurance.

6. TERMINATION
Either party may terminate this Agreement upon 90 days written notice.
"""


class TestContractValue:
    def test_extracted_with_currency(self):
        f = facts(CONTRACT)["contract_value"][0]
        assert f.value["amount"] == 20_000_000.0
        assert f.value["currency"] == "USD"

    def test_has_source_reference(self):
        f = facts(CONTRACT)["contract_value"][0]
        assert f.source_reference == "Page 1"
        assert "Contract Value" in f.source_text

    def test_confidence_high(self):
        assert facts(CONTRACT)["contract_value"][0].confidence >= 0.9


class TestDates:
    def test_start_date(self):
        assert facts(CONTRACT)["start_date"][0].value == "2026-01-01"

    def test_end_date(self):
        assert facts(CONTRACT)["end_date"][0].value == "2028-12-31"


class TestDuration:
    def test_thirty_six_months(self):
        f = facts(CONTRACT)["duration"][0]
        assert f.value["months"] == 36


class TestPayment:
    def test_sixty_days(self):
        assert facts(CONTRACT)["payment_terms_days"][0].value == 60


class TestRates:
    def test_day_rate(self):
        f = facts(CONTRACT)["day_rate"][0]
        assert f.value == {"amount": 25000.0, "currency": "USD"}

    def test_standby_rate(self):
        f = facts(CONTRACT)["standby_rate"][0]
        assert f.value["amount"] == 12500.0


class TestAvailability:
    def test_98_percent(self):
        assert facts(CONTRACT)["availability_target"][0].value == 98.0


class TestLiquidatedDamages:
    def test_rate_per_day(self):
        f = facts(CONTRACT)["ld_rate"][0]
        assert f.value["amount"] == 10_000.0
        assert f.value["per"] == "day"


class TestLiability:
    def test_liability_cap(self):
        f = facts(CONTRACT)["liability_cap"][0]
        assert f.value["amount"] == 5_000_000.0

    def test_unlimited_flag(self):
        text = "The Contractor shall accept unlimited liability for all claims."
        f = facts(text)["unlimited_liability"][0]
        assert f.value is True
        assert f.confidence >= 0.9

    def test_uncapped_flag(self):
        text = "Liability shall be uncapped under this Agreement."
        assert facts(text)["unlimited_liability"][0].value is True


class TestTermination:
    def test_notice_days(self):
        assert facts(CONTRACT)["termination_notice_days"][0].value == 90


class TestPercentages:
    def test_escalation(self):
        assert facts(CONTRACT)["escalation_pct"][0].value == 5.0

    def test_withholding(self):
        assert facts(CONTRACT)["withholding_tax_pct"][0].value == 10.0

    def test_retention(self):
        assert facts(CONTRACT)["retention_pct"][0].value == 10.0

    def test_nigerian_content(self):
        assert facts(CONTRACT)["nigerian_content_pct"][0].value == 45.0


class TestParties:
    def test_client(self):
        assert facts(CONTRACT)["client"][0].value == "Omega Energy Limited"

    def test_contractor(self):
        assert facts(CONTRACT)["contractor"][0].value == "DBS Drilling Services Ltd"


class TestDeduplication:
    def test_same_value_across_spans_kept_once(self):
        spans = [
            TextSpan(text="Contract Value: USD 20,000,000", source_reference="Page 1"),
            TextSpan(text="The Contract Value is USD 20,000,000", source_reference="Page 2"),
        ]
        found = [f for f in extract_facts(spans) if f.key == "contract_value"]
        assert len(found) == 1
        assert found[0].source_reference == "Page 1"


class TestNoFalsePositives:
    def test_duration_not_captured_as_money(self):
        f = facts("The term is 36 months.")
        assert "contract_value" not in f
        assert "day_rate" not in f

    def test_random_number_no_fact(self):
        f = facts("Reference number 4553 issued.")
        assert "contract_value" not in f
