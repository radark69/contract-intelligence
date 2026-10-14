import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

RISK_PDF_TEXT = """\
1. COMMERCIAL
CLIENT: Omega Energy Limited
CONTRACTOR: DBS Drilling Services Ltd
Contract Value: USD 20,000,000
Payment terms: within 75 days of invoice
Retention: 15%

2. TERM
This Agreement shall commence on 1 January 2026 and continue for 36 months.

3. LIABILITY
The Contractor shall accept unlimited liability for all claims howsoever arising.

4. LIQUIDATED DAMAGES
Liquidated damages shall apply for any delay to the works.

5. TERMINATION
Either party may terminate this Agreement upon 14 days written notice.
"""


def make_risk_pdf_bytes() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line in RISK_PDF_TEXT.splitlines():
        c.drawString(60, y, line)
        y -= 16
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
async def analyzed_doc(client):
    resp = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("risk.pdf", make_risk_pdf_bytes(), "application/pdf")},
    )
    doc_id = resp.json()["id"]
    await client.post(f"/api/v1/documents/{doc_id}/extract")
    resp = await client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert resp.status_code == 202, resp.text
    # background task completes before response in test client
    yield doc_id
    await client.delete(f"/api/v1/documents/{doc_id}")


class TestAnalyzeEndpoint:
    async def test_requires_extraction(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("raw.pdf", make_risk_pdf_bytes(), "application/pdf")},
        )
        doc_id = resp.json()["id"]
        resp = await client.post(f"/api/v1/documents/{doc_id}/analyze")
        assert resp.status_code == 409

    async def test_missing_document_404(self, client):
        resp = await client.post("/api/v1/documents/00000000-0000-0000-0000-000000000000/analyze")
        assert resp.status_code == 404


class TestFindings:
    async def test_findings_produced(self, client, analyzed_doc):
        findings = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        assert findings
        rules = {f["dbs_policy_rule"] for f in findings}
        assert "LIABILITY-001" in rules  # uncapped clause -> reject
        assert "PAYMENT-001" in rules  # 75 days fact -> escalate
        assert "MISSING-INFO" in rules or "LIQUIDATED_DAMAGES-001" in rules

    async def test_uncapped_is_critical_reject(self, client, analyzed_doc):
        findings = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        f = next(x for x in findings if x["dbs_policy_rule"] == "LIABILITY-001")
        assert f["severity"] == "critical"
        assert "unlimited liability" in f["source_text"].lower()
        assert f["source_reference"].startswith("Page ")
        assert f["clause_id"] is not None

    async def test_sorted_by_severity(self, client, analyzed_doc):
        findings = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        order = ["critical", "high", "medium", "low", "informational"]
        ranks = [order.index(f["severity"]) for f in findings]
        assert ranks == sorted(ranks)

    async def test_every_finding_has_evidence(self, client, analyzed_doc):
        findings = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        for f in findings:
            assert f["source_reference"]
            assert f["source_text"]
            assert f["recommendation"]
            assert 0 < f["confidence"] <= 1

    async def test_severity_filter(self, client, analyzed_doc):
        findings = (
            await client.get(f"/api/v1/documents/{analyzed_doc}/findings?severity=critical")
        ).json()
        assert findings
        assert all(f["severity"] == "critical" for f in findings)

    async def test_rule_filter(self, client, analyzed_doc):
        findings = (
            await client.get(
                f"/api/v1/documents/{analyzed_doc}/findings?dbs_policy_rule=LIABILITY-001"
            )
        ).json()
        assert findings
        assert all(f["dbs_policy_rule"] == "LIABILITY-001" for f in findings)

    async def test_rerun_is_idempotent(self, client, analyzed_doc):
        first = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        await client.post(f"/api/v1/documents/{analyzed_doc}/analyze")
        second = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        assert len(first) == len(second)
        assert [f["finding"] for f in first] == [f["finding"] for f in second]

    async def test_no_duplicate_rule_findings(self, client, analyzed_doc):
        findings = (await client.get(f"/api/v1/documents/{analyzed_doc}/findings")).json()
        # distinct findings: rule + clause + text uniquely identify a row
        keys = [(f["dbs_policy_rule"], f["clause_id"], f["finding"]) for f in findings]
        assert len(keys) == len(set(keys))
        # fact-level duplicate suppressed when clause evidence exists
        payment = [f for f in findings if f["dbs_policy_rule"] == "PAYMENT-001"]
        assert len(payment) == 1
        assert payment[0]["clause_id"] is not None

    async def test_missing_document_findings_404(self, client):
        resp = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/findings")
        assert resp.status_code == 404


class TestRiskRegister:
    async def test_register_shape(self, client, analyzed_doc):
        reg = (await client.get(f"/api/v1/documents/{analyzed_doc}/risk-register")).json()
        assert reg["total"] >= 3
        assert reg["rows"]
        row = reg["rows"][0]
        for field in (
            "id",
            "severity",
            "category",
            "clause",
            "finding",
            "exposure",
            "dbs_position",
            "required_action",
        ):
            assert field in row

    async def test_register_counts_match_rows(self, client, analyzed_doc):
        reg = (await client.get(f"/api/v1/documents/{analyzed_doc}/risk-register")).json()
        assert sum(reg["severity_counts"].values()) == reg["total"]

    async def test_register_flags_playbook_approval_rules(self, client, analyzed_doc):
        reg = (await client.get(f"/api/v1/documents/{analyzed_doc}/risk-register")).json()
        assert "LIABILITY-001" in reg["management_approval_rule_ids"]

    async def test_register_sorted_by_severity(self, client, analyzed_doc):
        reg = (await client.get(f"/api/v1/documents/{analyzed_doc}/risk-register")).json()
        order = ["critical", "high", "medium", "low", "informational"]
        ranks = [order.index(r["severity"]) for r in reg["rows"]]
        assert ranks == sorted(ranks)
