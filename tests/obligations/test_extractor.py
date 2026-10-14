from uuid import uuid4

from app.obligations.extractor import extract_from_clause, extract_obligations
from app.storage.models import Clause


def clause(text: str, category: str = "general", number: str = "1") -> Clause:
    return Clause(
        id=uuid4(),
        document_id=uuid4(),
        raw_text=text,
        category=category,
        clause_number=number,
        source_page=2,
    )


class TestExtractFromClause:
    def test_contractor_obligation(self):
        obs = extract_from_clause(
            clause("Contractor shall maintain the equipment in good working order.")
        )
        assert len(obs) == 1
        ob = obs[0]
        assert ob.party == "Contractor"
        assert "maintain the equipment" in ob.obligation
        assert ob.source_reference == "Page 2 → Clause 1"

    def test_client_obligation(self):
        obs = extract_from_clause(clause("Client shall provide site access within 7 days."))
        assert obs[0].party == "Client"

    def test_trigger_detected(self):
        obs = extract_from_clause(
            clause("Contractor shall demobilise upon termination of this Agreement.")
        )
        assert obs[0].trigger is not None
        assert "termination" in obs[0].trigger.lower()

    def test_frequency_detected(self):
        obs = extract_from_clause(clause("Contractor shall report HSE statistics daily."))
        assert obs[0].frequency == "daily"

    def test_no_mandatory_verb_no_obligation(self):
        obs = extract_from_clause(clause("The equipment is in good condition."))
        assert obs == []

    def test_descriptive_sentence_skipped(self):
        obs = extract_from_clause(clause("This Agreement shall commence on 1 January 2026."))
        assert obs == []  # no party resolvable

    def test_is_required_to_variant(self):
        obs = extract_from_clause(
            clause("Contractor is required to hold insurance throughout the term.")
        )
        assert obs[0].party == "Contractor"


class TestExtractObligations:
    def test_dedupes_across_clauses(self):
        c1 = clause("Contractor shall insure all equipment.", number="1")
        c2 = clause("Contractor shall insure all equipment.", number="2")
        obs = extract_obligations([c1, c2])
        assert len(obs) == 1

    def test_multiple_distinct(self):
        c1 = clause("Contractor shall insure all equipment.")
        c2 = clause("Client shall pay invoices within 30 days.")
        obs = extract_obligations([c1, c2])
        assert len(obs) == 2

    def test_empty_input(self):
        assert extract_obligations([]) == []
