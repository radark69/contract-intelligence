import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://rb@localhost:5432/contract_intel_test"
os.environ["TESTING"] = "true"

import io  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from fastapi import UploadFile  # noqa: E402
from sqlalchemy import text  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.storage.database import Base, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()





@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_upload(filename: str, content: bytes) -> UploadFile:
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.size = len(content)
    file.file = io.BytesIO(content)
    return file


@pytest.fixture
def sample_pdf_upload() -> UploadFile:
    content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF"
    return make_upload("contract.pdf", content)


@pytest.fixture
def sample_xlsx_upload() -> UploadFile:
    content = b"PK\x03\x04" + b"\x00" * 64
    return make_upload("terms.xlsx", content)


@pytest.fixture
def docx_upload() -> UploadFile:
    return make_upload("contract.docx", b"not allowed")
