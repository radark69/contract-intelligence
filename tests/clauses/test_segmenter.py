from app.clauses.segmenter import (
    ClauseDraft,
    segment_pdf_pages,
    segment_xlsx_sheets,
)
from app.extraction.pdf import PageResult
from app.extraction.xlsx import SheetResult

CONTRACT_PAGE_1 = """\
1. DEFINITIONS AND INTERPRETATION
In this Agreement the following terms shall have the meanings assigned to them.

2. SCOPE OF WORK
2.1 The Contractor shall provide two 2000HP drilling rigs.
2.2 The Contractor shall provide all personnel required for operations.

3. TERM
The Agreement shall commence on 1 January 2026.
"""

CONTRACT_PAGE_2 = """\
Article 4. Liability
4.1 The liability of the Contractor shall be capped at the contract value.

SCHEDULE 1 - RATES
Day rate: USD 25,000
"""


def make_pages(*texts: str) -> list[PageResult]:
    return [PageResult(page_number=i + 1, text=text) for i, text in enumerate(texts)]


class TestPdfSegmentation:
    def test_top_level_headings_detected(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_1))
        numbers = [d.clause_number for d in drafts]
        assert numbers == ["1", "2", "2.1", "2.2", "3"]

    def test_heading_title_and_section(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_1))
        first = drafts[0]
        assert first.title == "DEFINITIONS AND INTERPRETATION"
        assert first.section == "DEFINITIONS AND INTERPRETATION"

    def test_subclause_inherits_section(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_1))
        sub = [d for d in drafts if d.clause_number == "2.1"][0]
        assert sub.section == "SCOPE OF WORK"

    def test_source_page_recorded(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_1, CONTRACT_PAGE_2))
        article = [d for d in drafts if d.clause_number == "4"][0]
        assert article.source_page == 2
        first = [d for d in drafts if d.clause_number == "1"][0]
        assert first.source_page == 1

    def test_article_pattern(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_2))
        article = drafts[0]
        assert article.clause_number == "4"
        assert article.title == "Liability"
        assert article.section == "Liability"

    def test_schedule_heading_detected(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_2))
        titles = [d.title for d in drafts]
        assert "SCHEDULE 1 - RATES" in titles

    def test_body_text_attached_to_clause(self):
        drafts = segment_pdf_pages(make_pages(CONTRACT_PAGE_1))
        term = [d for d in drafts if d.clause_number == "3"][0]
        assert "36 months" not in term.raw_text  # fixture says "1 January 2026"
        assert "1 January 2026" in term.raw_text

    def test_long_sentence_not_treated_as_heading(self):
        pages = make_pages("1. The Contractor shall provide services for the entire duration.")
        drafts = segment_pdf_pages(pages)
        assert drafts[0].title is None

    def test_empty_text_produces_no_drafts(self):
        assert segment_pdf_pages(make_pages("", "   \n\n")) == []


class TestXlsxSegmentation:
    def _sheet(self) -> SheetResult:
        return SheetResult(
            position=1,
            sheet_name="Commercial Terms",
            is_hidden=False,
            row_count=10,
            col_count=3,
            merged_ranges=["A1:C1"],
            data=[
                {
                    "row": 3,
                    "range": "A3:C3",
                    "cells": [
                        {
                            "ref": "A3",
                            "row": 3,
                            "col": 1,
                            "value": "1. Contract Value",
                            "formula": None,
                            "comment": None,
                        },
                        {
                            "ref": "B3",
                            "row": 3,
                            "col": 2,
                            "value": 20000000,
                            "formula": None,
                            "comment": None,
                        },
                    ],
                },
                {
                    "row": 4,
                    "range": "A4:C4",
                    "cells": [
                        {
                            "ref": "A4",
                            "row": 4,
                            "col": 1,
                            "value": "Payment Terms",
                            "formula": None,
                            "comment": None,
                        },
                        {
                            "ref": "B4",
                            "row": 4,
                            "col": 2,
                            "value": "Net 60",
                            "formula": None,
                            "comment": None,
                        },
                    ],
                },
            ],
        )

    def test_row_becomes_clause_with_sheet_reference(self):
        drafts = segment_xlsx_sheets([self._sheet()])
        assert len(drafts) == 2
        assert drafts[0].source_sheet == "Commercial Terms"
        assert drafts[0].source_range == "A3:C3"

    def test_numeric_label_parsed_as_clause_number(self):
        drafts = segment_xlsx_sheets([self._sheet()])
        assert drafts[0].clause_number == "1"
        assert drafts[0].title == "Contract Value"

    def test_plain_label_becomes_title(self):
        drafts = segment_xlsx_sheets([self._sheet()])
        assert drafts[1].clause_number is None
        assert drafts[1].title == "Payment Terms"

    def test_raw_text_contains_all_values(self):
        drafts = segment_xlsx_sheets([self._sheet()])
        assert "20000000" in drafts[0].raw_text
        assert "Net 60" in drafts[1].raw_text

    def test_draft_type(self):
        drafts = segment_xlsx_sheets([self._sheet()])
        assert all(isinstance(d, ClauseDraft) for d in drafts)
