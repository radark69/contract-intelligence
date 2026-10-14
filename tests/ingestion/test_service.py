import io
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.ingestion.service import FileIngestionService
from app.storage.models import DocumentType


@pytest.fixture
def ingestion_service():
    return FileIngestionService()


@pytest.fixture
def mock_pdf_file():
    content = b"%PDF-1.4 test pdf content"
    file = MagicMock(spec=UploadFile)
    file.filename = "test.pdf"
    file.size = len(content)
    file.file = io.BytesIO(content)
    return file


@pytest.fixture
def mock_xlsx_file():
    content = b"PK\x03\x04 test xlsx content"
    file = MagicMock(spec=UploadFile)
    file.filename = "test.xlsx"
    file.size = len(content)
    file.file = io.BytesIO(content)
    return file


class TestFileIngestionService:
    def test_get_document_type_pdf(self, ingestion_service):
        assert ingestion_service._get_document_type("test.pdf") == DocumentType.PDF
        assert ingestion_service._get_document_type("TEST.PDF") == DocumentType.PDF

    def test_get_document_type_xlsx(self, ingestion_service):
        assert ingestion_service._get_document_type("test.xlsx") == DocumentType.XLSX
        assert ingestion_service._get_document_type("test.xls") == DocumentType.XLSX

    def test_get_document_type_invalid(self, ingestion_service):
        with pytest.raises(HTTPException):
            ingestion_service._get_document_type("test.docx")

    def test_validate_file_size_ok(self, ingestion_service, mock_pdf_file):
        ingestion_service._validate_file(mock_pdf_file)

    def test_validate_file_size_exceeds(self, ingestion_service):
        file = MagicMock(spec=UploadFile)
        file.filename = "test.pdf"
        file.size = 200 * 1024 * 1024  # 200MB
        file.file = io.BytesIO(b"x")
        with pytest.raises(HTTPException) as exc:
            ingestion_service._validate_file(file)
        assert "exceeds maximum allowed" in str(exc.value)

    def test_validate_file_type_invalid(self, ingestion_service):
        file = MagicMock(spec=UploadFile)
        file.filename = "test.docx"
        file.size = 1024
        file.file = io.BytesIO(b"x")
        with pytest.raises(HTTPException) as exc:
            ingestion_service._validate_file(file)
        assert "not allowed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_compute_hash(self, ingestion_service, mock_pdf_file):
        hash1 = await ingestion_service._compute_hash(mock_pdf_file.file)
        hash2 = await ingestion_service._compute_hash(mock_pdf_file.file)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
