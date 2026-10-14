import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import text
from app.storage.database import engine


@pytest.fixture(scope="module", autouse=True)
async def _clean_db_module():
    """Clear database at module start for isolation.""" 
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE audit_logs, users, findings, obligations, economic_exposures, contract_facts, extracted_tables, clauses, document_pages, document_sheets, documents RESTART IDENTITY CASCADE")
        )

PDF_TEXT = """\
1. COMMERCIAL
CLIENT: Omega Energy Limited
Contract Value: USD 20,000,000
Invoices require prior written approval by the Client.

2. TERM
This Agreement shall commence on 1 January 2026 and continue for 36 months.

3. LIABILITY
The Contractor shall accept unlimited liability for all claims howsoever arising.

4. LIQUIDATED DAMAGES
Liquidated damages shall apply for any delay to the works.

5. TERMINATION
Client may terminate this Agreement for convenience upon 30 days notice.

6. OBLIGATIONS
Contractor shall maintain the equipment in good working order daily.
Client shall provide site access within 7 days of the effective date.
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
async def doc(client):
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("s6.pdf", make_pdf(), "application/pdf")},
    )
    doc_id = resp.json()["id"]
    await client.post(f"/api/v1/documents/{doc_id}/extract")
    yield doc_id
    # Cleanup
    await client.delete(f"/api/v1/documents/{doc_id}")


class TestCrossClauseFindings:
    async def test_xc_ld_uncapped_finding(self, client, doc):
        findings = (await client.get(f"/api/v1/documents/{doc}/findings")).json()
        xc = [f for f in findings if f["dbs_policy_rule"].startswith("XC-")]
        assert xc
        ids = {f["dbs_policy_rule"] for f in xc}
        assert "XC-LD-UNCAPPED" in ids

    async def test_xc_evidence_links_both_clauses(self, client, doc):
        findings = (
            await client.get(f"/api/v1/documents/{doc}/findings?dbs_policy_rule=XC-LD-UNCAPPED")
        ).json()
        assert len(findings) == 1
        f = findings[0]
        assert f["severity"] == "critical"
        assert f["clause_id"] is not None
        assert "Page 1" in f["source_reference"]
        assert "interacts with" in f["source_reference"]
        assert f["source_text"]

    async def test_approval_without_deemed_detected(self, client, doc):
        findings = (
            await client.get(f"/api/v1/documents/{doc}/findings?dbs_policy_rule=XC-APPROVAL-NODEEM")
        ).json()
        assert len(findings) == 1
        assert findings[0]["severity"] == "high"

    async def test_register_includes_xc_rows(self, client, doc):
        reg = (await client.get(f"/api/v1/documents/{doc}/risk-register")).json()
        rules = {r["dbs_policy_rule"] for r in reg["rows"]}
        assert any(r.startswith("XC-") for r in rules)


class TestObligations:
    async def test_obligations_extracted(self, client, doc):
        obs = (await client.get(f"/api/v1/documents/{doc}/obligations")).json()
        assert obs
        texts = " | ".join(o["obligation"] for o in obs)
        assert "maintain the equipment" in texts
        assert "site access" in texts

    async def test_obligation_fields(self, client, doc):
        obs = (await client.get(f"/api/v1/documents/{doc}/obligations")).json()
        o = obs[0]
        for field in ("id", "party", "obligation", "source_reference"):
            assert field in o
        assert o["party"] in ("Client", "Contractor", "Both")
        assert o["source_reference"]

    async def test_party_filter(self, client, doc):
        obs = (await client.get(f"/api/v1/documents/{doc}/obligations?party=Client")).json()
        assert obs
        assert all(o["party"] == "Client" for o in obs)

    async def test_rerun_idempotent(self, client, doc):
        first = (await client.get(f"/api/v1/documents/{doc}/obligations")).json()
        await client.post(f"/api/v1/documents/{doc}/obligations")
        second = (await client.get(f"/api/v1/documents/{doc}/obligations")).json()
        assert len(first) == len(second)

    async def test_before_extraction_409(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("raw6.pdf", make_pdf(), "application/pdf")},
        )
        doc_id = resp.json()["id"]
        resp = await client.post(f"/api/v1/documents/{doc_id}/obligations")
        assert resp.status_code == 409

    async def test_missing_document_404(self, client):
        resp = await client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/obligations"
        )
        assert resp.status_code == 404
