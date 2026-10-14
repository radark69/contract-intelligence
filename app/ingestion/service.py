import hashlib
import uuid
from pathlib import Path
from typing import BinaryIO

import aiofiles
import structlog
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.storage.database import async_session_maker
from app.storage.models import Document, DocumentStatus, DocumentType

logger = structlog.get_logger()


class FileIngestionService:
    def __init__(self) -> None:
        self.upload_dir = settings.storage_path / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def _get_by_hash(self, file_hash: str) -> Document | None:
        async with async_session_maker() as session:
            result = await session.execute(select(Document).where(Document.file_hash == file_hash))
            return result.scalar_one_or_none()

    def _get_document_type(self, filename: str) -> DocumentType:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return DocumentType.PDF
        elif suffix in (".xlsx", ".xls"):
            return DocumentType.XLSX
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    def _validate_file(self, file: UploadFile) -> None:
        if file.size and file.size > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed ({settings.max_file_size_mb}MB)",
            )
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is required")
        suffix = Path(file.filename).suffix.lower()
        if suffix not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type {suffix} not allowed. Allowed: {settings.allowed_extensions}",
            )

    async def _compute_hash(self, file: BinaryIO) -> str:
        hasher = hashlib.sha256()
        while chunk := file.read(8192):
            hasher.update(chunk)
        file.seek(0)
        return hasher.hexdigest()

    async def _save_file(self, file: UploadFile, file_hash: str) -> Path:
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is required")
        suffix = Path(file.filename).suffix.lower()
        stored_filename = f"{file_hash}{suffix}"
        file_path = self.upload_dir / stored_filename

        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                await f.write(chunk)

        return file_path

    async def ingest(self, file: UploadFile, uploaded_by: str | None = None) -> Document:
        self._validate_file(file)

        file_hash = await self._compute_hash(file.file)
        logger.info("File hashed", filename=file.filename, hash=file_hash[:16])

        existing = await self._get_by_hash(file_hash)
        if existing:
            logger.info(
                "Duplicate file detected", hash=file_hash[:16], existing_id=str(existing.id)
            )
            return existing

        file_path = await self._save_file(file, file_hash)
        logger.info("File saved", path=str(file_path))

        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is required")
        doc_type = self._get_document_type(file.filename)

        document = Document(
            filename=file.filename,
            file_hash=file_hash,
            file_size=file.size or file_path.stat().st_size,
            document_type=doc_type,
            status=DocumentStatus.UPLOADED,
            uploaded_by=uploaded_by,
        )

        async with async_session_maker() as session:
            session.add(document)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await self._get_by_hash(file_hash)
                if existing:
                    logger.info(
                        "Duplicate uploaded concurrently",
                        hash=file_hash[:16],
                        existing_id=str(existing.id),
                    )
                    return existing
                raise
            await session.refresh(document)

        logger.info("Document record created", document_id=str(document.id))
        return document

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        async with async_session_maker() as session:
            return await session.get(Document, document_id)

    async def update_status(
        self, document_id: uuid.UUID, status: DocumentStatus, error: str | None = None
    ) -> Document:
        async with async_session_maker() as session:
            document = await session.get(Document, document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            document.status = status
            if error:
                document.error_message = error
            await session.commit()
            await session.refresh(document)
            return document


ingestion_service = FileIngestionService()
