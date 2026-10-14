import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PDF_TEXT = """\
1. COMMERCIAL
CLIENT: Omega Energy Limited
Contract Value: USD 20,000,000
Payment terms: within 75 days of invoice
Day Rate: USD 25,000

2. TERM
This Agreement shall commence on 1 January 2026 and continue for 36 months.

4. LIQUIDATED DAMAGES
Liquidated damages of USD 10,000 per day shall apply for each day of delay.

5. INSURANCE
Contractor shall maintain insurance as required by the Client.
"""


def make_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line in PDF_TEXT.splitlines():
        c.drawString(60, y, line)
        y -= 16
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
async def analyzed_doc(client):
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("econ.pdf", make_pdf(), "application/pdf")},
    )
    doc_id = resp.json()["id"]
    await client.post(f"/api/v1/documents/{doc_id}/extract")
    yield doc_id
    await client.delete(f"/api/v1/documents/{doc_id}")


class TestExposuresEndpoint:
    async def test_exposures_computed(self, client, analyzed_doc):
        data = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        rows = data["exposures"]
        assert rows
        scenarios = {r["scenario"] for r in rows}
        assert "stated value" in scenarios
        assert "day-rate run-rate" in scenarios
        assert "worst case (full-term accrual)" in scenarios

    async def test_exposure_shape(self, client, analyzed_doc):
        data = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        r = data["exposures"][0]
        for field in (
            "id",
            "scenario",
            "assumption",
            "formula",
            "result",
            "currency",
            "source_reference",
        ):
            assert field in r

    async def test_currency_usd(self, client, analyzed_doc):
        data = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        assert all(r["currency"] == "USD" for r in data["exposures"])

    async def test_cannot_calculate_notes(self, client, analyzed_doc):
        data = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        notes = {c["metric"]: c["reason"] for c in data["cannot_calculate"]}
        assert "gross contribution and margin" in notes
        assert "direct cost" in notes["gross contribution and margin"]

    async def test_working_capital_value(self, client, analyzed_doc):
        data = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        wc = next(r for r in data["exposures"] if r["scenario"] == "receivables outstanding")
        assert wc["result"] == pytest.approx(20_000_000.0 * 75 / 365.0)

    async def test_missing_document_404(self, client):
        resp = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/exposures")
        assert resp.status_code == 404

    async def test_idempotent_rerun(self, client, analyzed_doc):
        first = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        await client.post(f"/api/v1/documents/{analyzed_doc}/analyze")
        second = (await client.get(f"/api/v1/documents/{analyzed_doc}/exposures")).json()
        assert len(first["exposures"]) == len(second["exposures"])
