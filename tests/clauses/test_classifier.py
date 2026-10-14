from app.clauses.classifier import classify_clause, source_reference


class TestClassifyClause:
    def test_liability_by_title(self):
        assert classify_clause("Limitation of Liability", "") == "liability"

    def test_indemnity_wins_over_liability(self):
        assert classify_clause("Indemnities", " Contractor shall indemnify Client") == "indemnity"

    def test_termination(self):
        assert classify_clause(None, "Either party may terminate this Agreement") == "termination"

    def test_payment(self):
        assert classify_clause("Payment", "Invoice within 30 days") == "payment"

    def test_hse_keywords(self):
        assert classify_clause(None, "The Contractor shall comply with PTW procedures") == "hse"

    def test_availability(self):
        assert classify_clause("Availability", "98% availability required") == "availability"

    def test_ld_before_payment(self):
        text = "Liquidated damages of USD 10,000 per day shall apply to late payment"
        assert classify_clause(None, text) == "liquidated_damages"

    def test_nigerian_content(self):
        assert classify_clause(None, "NCDMB Nigerian Content obligations apply") == "regulatory"

    def test_insurance(self):
        assert classify_clause("Insurance", "Maintain cover of USD 10M") == "insurance"

    def test_downtime(self):
        assert classify_clause(None, "NPT shall not exceed 5%") == "downtime_npt"

    def test_governing_law(self):
        assert classify_clause(None, "Governed by the laws of Nigeria") == "dispute_resolution"

    def test_default_general(self):
        assert classify_clause(None, "This Agreement is made on 1 January 2026") == "general"

    def test_title_match_takes_precedence(self):
        assert classify_clause("Termination", "notice period 30 days") == "termination"


class TestSourceReference:
    def test_pdf_page_reference(self):
        assert source_reference(page=27) == "Page 27"

    def test_xlsx_sheet_reference(self):
        assert source_reference(sheet="Commercial Terms", cell_range="B14:F18") == (
            "Sheet: Commercial Terms, Range: B14:F18"
        )

    def test_xlsx_sheet_without_range(self):
        assert source_reference(sheet="Rates") == "Sheet: Rates"

    def test_unknown(self):
        assert source_reference() == "Unknown source"
