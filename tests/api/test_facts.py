import io

import pytest

FACTS_PDF_TEXT = """\
1. COMMERCIAL
CLIENT: Omega Energy Limited
CONTRACTOR: DBS Drilling Services Ltd
Contract Value: USD 20,000,000
Payment terms: within 60 days of invoice
Day Rate: USD 25,000

2. TERM
This Agreement shall commence on 1 January 2026 and continue for 36 months.

3. OPERATIONS
Contractor guarantees 98% availability of the rigs.

4. LIABILITY
The liability of the Contractor shall be capped at USD 5,000,000.

5. TERMINATION
Either party may terminate this Agreement upon 90 days written notice.
"""


def make_facts_pdf_bytes() -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line in FACTS_PDF_TEXT.splitlines():
        c.drawString(60, y, line)
        y -= 16
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
async def extracted_doc(client):
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("facts.pdf", make_facts_pdf_bytes(), "application/pdf")},
    )
    doc_id = resp.json()["id"]
    await client.post(f"/api/v1/documents/{doc_id}/extract")
    yield doc_id
    await client.delete(f"/api/v1/documents/{doc_id}")


class TestFactsPipeline:
    async def test_extract_chains_fact_extraction(self, client, extracted_doc):
        facts = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        keys = {f["key"] for f in facts}
        assert "contract_value" in keys
        assert "payment_terms_days" in keys

    async def test_document_denormalized(self, client, extracted_doc):
        doc = (await client.get(f"/api/v1/documents/{extracted_doc}")).json()
        assert float(doc["contract_value"]) == 20_000_000
        assert doc["currency"] == "USD"
        assert doc["start_date"].startswith("2026-01-01")

    async def test_fact_values(self, client, extracted_doc):
        facts = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        by_key = {f["key"]: f for f in facts}
        assert by_key["payment_terms_days"]["value"] == 60
        assert by_key["availability_target"]["value"] == 98.0
        assert by_key["liability_cap"]["value"]["amount"] == 5_000_000
        assert by_key["duration"]["value"]["months"] == 36
        assert by_key["termination_notice_days"]["value"] == 90

    async def test_facts_have_source_references(self, client, extracted_doc):
        facts = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        for f in facts:
            assert f["source_reference"].startswith("Page ")
            assert f["source_text"]
            assert 0 < f["confidence"] <= 1

    async def test_facts_linked_to_clauses(self, client, extracted_doc):
        facts = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        clauses = (await client.get(f"/api/v1/documents/{extracted_doc}/clauses")).json()
        clause_ids = {c["id"] for c in clauses}
        linked = [f for f in facts if f["clause_id"]]
        assert linked
        assert all(f["clause_id"] in clause_ids for f in linked)

    async def test_key_filter(self, client, extracted_doc):
        facts = (
            await client.get(f"/api/v1/documents/{extracted_doc}/facts?key=contract_value")
        ).json()
        assert len(facts) >= 1
        assert all(f["key"] == "contract_value" for f in facts)


class TestStandaloneFactsEndpoint:
    async def test_rerun_facts_endpoint(self, client, extracted_doc):
        resp = await client.post(f"/api/v1/documents/{extracted_doc}/facts")
        assert resp.status_code == 202
        facts = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        assert facts

    async def test_facts_before_extraction_rejected(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("raw.pdf", make_facts_pdf_bytes(), "application/pdf")},
        )
        doc_id = resp.json()["id"]
        resp = await client.post(f"/api/v1/documents/{doc_id}/facts")
        assert resp.status_code == 409

    async def test_missing_document_404(self, client):
        resp = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/facts")
        assert resp.status_code == 404

    async def test_rerun_is_idempotent(self, client, extracted_doc):
        first = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        await client.post(f"/api/v1/documents/{extracted_doc}/facts")
        second = (await client.get(f"/api/v1/documents/{extracted_doc}/facts")).json()
        assert len(first) == len(second)
