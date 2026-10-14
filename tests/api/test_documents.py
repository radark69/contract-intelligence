PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF"
XLSX_BYTES = b"PK\x03\x04" + b"\x00" * 64


class TestHealth:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestUploadDocument:
    async def test_upload_pdf(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
            data={"uploaded_by": "tester"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "pdf"
        assert data["status"] == "uploaded"
        assert len(data["file_hash"]) == 64

    async def test_upload_xlsx(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("terms.xlsx", XLSX_BYTES, "application/vnd.ms-excel")},
        )
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "xlsx"

    async def test_upload_rejects_unsupported_type(self, client):
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("contract.docx", b"stuff", "application/msword")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    async def test_upload_deduplicates_by_hash(self, client):
        first = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("dup.pdf", PDF_BYTES, "application/pdf")},
        )
        second = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("dup_renamed.pdf", PDF_BYTES, "application/pdf")},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]


class TestGetDocument:
    async def test_get_existing_document(self, client):
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("getme.pdf", PDF_BYTES, "application/pdf")},
        )
        doc_id = upload.json()["id"]
        resp = await client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id

    async def test_get_missing_document_returns_404(self, client):
        resp = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestListDocuments:
    async def test_list_returns_documents(self, client):
        await client.post(
            "/api/v1/documents/upload",
            files={"file": ("listed.pdf", PDF_BYTES, "application/pdf")},
        )
        resp = await client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1


class TestDeleteDocument:
    async def test_delete_existing_document(self, client):
        upload = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("deleteme.pdf", PDF_BYTES, "application/pdf")},
        )
        doc_id = upload.json()["id"]
        resp = await client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        get = await client.get(f"/api/v1/documents/{doc_id}")
        assert get.status_code == 404

    async def test_delete_missing_document_returns_404(self, client):
        resp = await client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
