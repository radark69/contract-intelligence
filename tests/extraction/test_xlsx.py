import pytest

from app.extraction.xlsx import XlsxExtractor

openpyxl = pytest.importorskip("openpyxl")


def build_workbook(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Commercial Terms"

    ws["A1"] = "Contract Schedule"
    ws.merge_cells("A1:C1")

    ws["A3"] = "1. Contract Value"
    ws["B3"] = 20000000
    ws["A4"] = "Payment Terms"
    ws["B4"] = "Net 60"
    ws["A5"] = "Availability"
    ws["B5"] = 0.98
    ws["B5"].number_format = "0%"
    ws["A6"] = "Effective Date"
    ws["B6"] = "2026-01-01"

    ws["C3"] = "=B3*0.1"
    ws["C3"].comment = openpyxl.comments.Comment("10% mobilisation advance", "commercial")

    hidden = wb.create_sheet("Internal Notes")
    hidden["A1"] = "internal margin assumptions"
    hidden.sheet_state = "hidden"

    wb.save(path)
    return path


@pytest.fixture
def workbook(tmp_path):
    path = tmp_path / "schedule.xlsx"
    return build_workbook(path)


class TestXlsxExtractor:
    def test_sheet_names_and_count(self, workbook):
        result = XlsxExtractor().extract(workbook)
        assert result.sheet_count == 2
        names = [s.sheet_name for s in result.sheets]
        assert names == ["Commercial Terms", "Internal Notes"]

    def test_hidden_sheet_flagged(self, workbook):
        result = XlsxExtractor().extract(workbook)
        hidden = [s for s in result.sheets if s.is_hidden]
        assert len(hidden) == 1
        assert hidden[0].sheet_name == "Internal Notes"
        assert any("Hidden sheet" in w for w in result.warnings)

    def test_hidden_sheet_data_still_extracted(self, workbook):
        result = XlsxExtractor().extract(workbook)
        hidden = [s for s in result.sheets if s.is_hidden][0]
        assert any(
            "internal margin" in str(cell["value"]) for row in hidden.data for cell in row["cells"]
        )

    def test_cell_values_with_coordinates(self, workbook):
        result = XlsxExtractor().extract(workbook)
        first = result.sheets[0]
        by_ref = {cell["ref"]: cell for row in first.data for cell in row["cells"]}
        assert by_ref["A3"]["value"] == "1. Contract Value"
        assert by_ref["B3"]["value"] == 20000000
        assert by_ref["B5"]["value"] == 0.98

    def test_formula_captured_separately_from_value(self, workbook):
        result = XlsxExtractor().extract(workbook)
        by_ref = {cell["ref"]: cell for row in result.sheets[0].data for cell in row["cells"]}
        assert by_ref["C3"]["formula"] == "=B3*0.1"

    def test_comment_extracted(self, workbook):
        result = XlsxExtractor().extract(workbook)
        by_ref = {cell["ref"]: cell for row in result.sheets[0].data for cell in row["cells"]}
        assert "mobilisation advance" in by_ref["C3"]["comment"]

    def test_merged_ranges_recorded(self, workbook):
        result = XlsxExtractor().extract(workbook)
        assert "A1:C1" in result.sheets[0].merged_ranges

    def test_row_and_col_counts(self, workbook):
        result = XlsxExtractor().extract(workbook)
        first = result.sheets[0]
        assert first.row_count >= 6
        assert first.col_count >= 3

    def test_serializable_output(self, workbook):
        import json

        result = XlsxExtractor().extract(workbook)
        for sheet in result.sheets:
            json.dumps(sheet.data)
            json.dumps(sheet.merged_ranges)
