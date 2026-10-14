import io

import pytest

PDF_TEXT = """\
1. DEFINITIONS AND INTERPRETATION
In this Agreement the following terms shall have the meanings assigned below.

2. SCOPE OF WORK
2.1 The Contractor shall provide two 2000HP drilling rigs for the campaign.
2.2 The Contractor shall provide all personnel required for safe operations.

3. PAYMENT
Invoices shall be submitted monthly and paid within sixty days of approval.

4. LIABILITY
The liability of the Contractor shall be unlimited for personal injury claims.
"""


def make_pdf_bytes() -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line in PDF_TEXT.splitlines():
        c.drawString(60, y, line)
        y -= 16
    c.showPage()
    c.save()
    return buf.getvalue()


def make_xlsx_bytes() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Commercial Terms"
    ws["A1"] = "1. Contract Value"
    ws["B1"] = 20000000
    ws["A2"] = "Payment Terms"
    ws["B2"] = "Net 60"
    hidden = wb.create_sheet("Internal")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "margin notes"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
async def uploaded_pdf(client):
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("extract_me.pdf", make_pdf_bytes(), "application/pdf")},
    )
    return resp.json()["id"]


@pytest.fixture
async def uploaded_xlsx(client):
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("schedule.xlsx", make_xlsx_bytes(), "application/vnd.ms-excel")},
    )
    return resp.json()["id"]


class TestPdfExtractionFlow:
    async def test_extract_sets_status_extracted(self, client, uploaded_pdf):
        resp = await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        assert resp.status_code == 202
        doc = await client.get(f"/api/v1/documents/{uploaded_pdf}")
        assert doc.json()["status"] == "extracted"
        assert doc.json()["page_count"] == 1

    async def test_pages_endpoint_returns_text(self, client, uploaded_pdf):
        await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        resp = await client.get(f"/api/v1/documents/{uploaded_pdf}/pages")
        assert resp.status_code == 200
        pages = resp.json()
        assert len(pages) == 1
        assert "SCOPE OF WORK" in pages[0]["text"]
        assert pages[0]["is_ocr"] is False

    async def test_clauses_endpoint_returns_segmented_clauses(self, client, uploaded_pdf):
        await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        resp = await client.get(f"/api/v1/documents/{uploaded_pdf}/clauses")
        clauses = resp.json()
        numbers = [c["clause_number"] for c in clauses]
        assert "1" in numbers
        assert "2.1" in numbers
        assert "4" in numbers

    async def test_clauses_have_page_references(self, client, uploaded_pdf):
        await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        clauses = (await client.get(f"/api/v1/documents/{uploaded_pdf}/clauses")).json()
        assert all(c["source_page"] == 1 for c in clauses)

    async def test_clauses_have_categories(self, client, uploaded_pdf):
        await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        clauses = (await client.get(f"/api/v1/documents/{uploaded_pdf}/clauses")).json()
        by_number = {c["clause_number"]: c for c in clauses}
        assert by_number["4"]["category"] == "liability"
        assert by_number["3"]["category"] == "payment"

    async def test_reextraction_is_idempotent(self, client, uploaded_pdf):
        await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        first = (await client.get(f"/api/v1/documents/{uploaded_pdf}/clauses")).json()
        await client.post(f"/api/v1/documents/{uploaded_pdf}/extract")
        second = (await client.get(f"/api/v1/documents/{uploaded_pdf}/clauses")).json()
        assert len(first) == len(second)


class TestXlsxExtractionFlow:
    async def test_extract_sets_sheet_count(self, client, uploaded_xlsx):
        await client.post(f"/api/v1/documents/{uploaded_xlsx}/extract")
        doc = (await client.get(f"/api/v1/documents/{uploaded_xlsx}")).json()
        assert doc["status"] == "extracted"
        assert doc["sheet_count"] == 2

    async def test_hidden_sheet_warning(self, client, uploaded_xlsx):
        await client.post(f"/api/v1/documents/{uploaded_xlsx}/extract")
        doc = (await client.get(f"/api/v1/documents/{uploaded_xlsx}")).json()
        assert any("Hidden sheet" in w for w in doc["warnings"])

    async def test_sheets_endpoint_summary_hides_data_by_default(self, client, uploaded_xlsx):
        await client.post(f"/api/v1/documents/{uploaded_xlsx}/extract")
        sheets = (await client.get(f"/api/v1/documents/{uploaded_xlsx}/sheets")).json()
        assert len(sheets) == 2
        assert "data" not in sheets[0]
        assert sheets[1]["is_hidden"] is True

    async def test_sheets_endpoint_include_data(self, client, uploaded_xlsx):
        await client.post(f"/api/v1/documents/{uploaded_xlsx}/extract")
        sheets = (
            await client.get(f"/api/v1/documents/{uploaded_xlsx}/sheets?include_data=true")
        ).json()
        assert "data" in sheets[0]

    async def test_clauses_reference_sheet_and_range(self, client, uploaded_xlsx):
        await client.post(f"/api/v1/documents/{uploaded_xlsx}/extract")
        clauses = (await client.get(f"/api/v1/documents/{uploaded_xlsx}/clauses")).json()
        assert len(clauses) >= 2
        assert clauses[0]["source_sheet"] == "Commercial Terms"
        assert clauses[0]["source_range"] is not None


class TestExtractionErrors:
    async def test_extract_missing_document_404(self, client):
        resp = await client.post("/api/v1/documents/00000000-0000-0000-0000-000000000000/extract")
        assert resp.status_code == 404

    async def test_pages_missing_document_404(self, client):
        resp = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/pages")
        assert resp.status_code == 404

    async def test_corrupt_pdf_marks_failed(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("broken.pdf", b"not a real pdf at all", "application/pdf")},
        )
        doc_id = resp.json()["id"]
        await client.post(f"/api/v1/documents/{doc_id}/extract")
        try:
            # test assertions here if any
            pass
        finally:
            await client.delete(f"/api/v1/documents/{doc_id}")
        doc = (await client.get(f"/api/v1/documents/{doc_id}")).json()
        assert doc["status"] == "failed"
        assert doc["error_message"]
