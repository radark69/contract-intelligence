import asyncio
import glob
import logging
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clauses.classifier import classify_clause
from app.clauses.segmenter import ClauseDraft, segment_pdf_pages, segment_xlsx_sheets
from app.config import settings
from app.extraction.pdf import PageResult, PdfExtractionResult, PdfExtractor
from app.extraction.xlsx import SheetResult, XlsxExtractionResult, XlsxExtractor
from app.storage.database import async_session_maker
from app.storage.models import (
    Clause,
    Document,
    DocumentPage,
    DocumentSheet,
    DocumentStatus,
    DocumentType,
    ExtractedTable,
)

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self) -> None:
        self.pdf_extractor = PdfExtractor(
            ocr_languages=settings.ocr_languages,
            tesseract_path=settings.tesseract_path,
        )
        self.xlsx_extractor = XlsxExtractor()

    def _resolve_file_path(self, document: Document) -> Path:
        matches = glob.glob(str(settings.storage_path / "uploads" / f"{document.file_hash}.*"))
        if not matches:
            raise FileNotFoundError(f"Stored file not found for hash {document.file_hash[:16]}")
        return Path(matches[0])

    async def extract_document(self, document_id: UUID) -> Document:
        async with async_session_maker() as session:
            document = await session.get(Document, document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            document.status = DocumentStatus.PROCESSING
            document.error_message = None
            await session.commit()

        try:
            return await self._run(document_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Extraction failed for %s", document_id)
            async with async_session_maker() as session:
                document = await session.get(Document, document_id)
                if document:
                    document.status = DocumentStatus.FAILED
                    document.error_message = f"{exc.__class__.__name__}: {exc}"
                    await session.commit()
                    return document
            raise

    async def _run(self, document_id: UUID) -> Document:
        async with async_session_maker() as session:
            document = await session.get(Document, document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            file_path = self._resolve_file_path(document)
            doc_type = document.document_type

        if doc_type == DocumentType.PDF:
            result: PdfExtractionResult | XlsxExtractionResult = await asyncio.to_thread(
                self.pdf_extractor.extract, file_path
            )
            assert isinstance(result, PdfExtractionResult)
            drafts = await self._persist_pdf(document_id, result.pages)
            warnings = result.warnings
            page_count: int | None = len(result.pages)
            sheet_count: int | None = None
        else:
            if file_path.suffix.lower() == ".xls":
                raise ValueError(
                    "Legacy .xls files are not supported yet — save as .xlsx and re-upload"
                )
            result = await asyncio.to_thread(self.xlsx_extractor.extract, file_path)
            assert isinstance(result, XlsxExtractionResult)
            drafts = await self._persist_xlsx(document_id, result.sheets)
            warnings = result.warnings
            page_count = None
            sheet_count = len(result.sheets)

        if not drafts:
            warnings.append("No clause-like structures detected — verify document readability")

        async with async_session_maker() as session:
            document = await session.get(Document, document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            document.status = DocumentStatus.EXTRACTED
            document.page_count = page_count
            document.sheet_count = sheet_count
            document.warnings = warnings or None
            await session.commit()
            await session.refresh(document)
            return document

    async def _clear_previous_extraction(self, document_id: UUID, session: AsyncSession) -> None:
        await session.execute(delete(Clause).where(Clause.document_id == document_id))
        await session.execute(
            delete(ExtractedTable).where(ExtractedTable.document_id == document_id)
        )
        await session.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
        await session.execute(delete(DocumentSheet).where(DocumentSheet.document_id == document_id))

    def _add_clauses(
        self, session: AsyncSession, document_id: UUID, drafts: list[ClauseDraft]
    ) -> None:
        for draft in drafts:
            session.add(
                Clause(
                    document_id=document_id,
                    section=draft.section,
                    clause_number=draft.clause_number,
                    title=draft.title,
                    raw_text=draft.raw_text,
                    source_page=draft.source_page,
                    source_sheet=draft.source_sheet,
                    source_range=draft.source_range,
                    category=classify_clause(draft.title, draft.raw_text),
                )
            )

    async def _persist_pdf(self, document_id: UUID, pages: list[PageResult]) -> list[ClauseDraft]:
        drafts = segment_pdf_pages(pages)
        async with async_session_maker() as session:
            await self._clear_previous_extraction(document_id, session)
            for page in pages:
                session.add(
                    DocumentPage(
                        document_id=document_id,
                        page_number=page.page_number,
                        text=page.text,
                        is_ocr=page.is_ocr,
                        table_count=page.table_count,
                    )
                )
                for i, table in enumerate(page.tables):
                    session.add(
                        ExtractedTable(
                            document_id=document_id,
                            position=i,
                            source_page=page.page_number,
                            rows=table,
                        )
                    )
            self._add_clauses(session, document_id, drafts)
            await session.commit()
        return drafts

    async def _persist_xlsx(
        self, document_id: UUID, sheets: list[SheetResult]
    ) -> list[ClauseDraft]:
        drafts = segment_xlsx_sheets(sheets)
        async with async_session_maker() as session:
            await self._clear_previous_extraction(document_id, session)
            for sheet in sheets:
                session.add(
                    DocumentSheet(
                        document_id=document_id,
                        position=sheet.position,
                        sheet_name=sheet.sheet_name,
                        is_hidden=sheet.is_hidden,
                        row_count=sheet.row_count,
                        col_count=sheet.col_count,
                        merged_ranges=sheet.merged_ranges,
                        data=sheet.data,
                    )
                )
            self._add_clauses(session, document_id, drafts)
            await session.commit()
        return drafts

    async def get_pages(self, document_id: UUID) -> list[dict]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(DocumentPage)
                .where(DocumentPage.document_id == document_id)
                .order_by(DocumentPage.page_number)
            )
            return [
                {
                    "page_number": p.page_number,
                    "text": p.text,
                    "is_ocr": p.is_ocr,
                    "table_count": p.table_count,
                }
                for p in result.scalars().all()
            ]

    async def get_sheets(self, document_id: UUID, include_data: bool = False) -> list[dict]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(DocumentSheet)
                .where(DocumentSheet.document_id == document_id)
                .order_by(DocumentSheet.position)
            )
            sheets = []
            for s in result.scalars().all():
                item = {
                    "sheet_name": s.sheet_name,
                    "is_hidden": s.is_hidden,
                    "row_count": s.row_count,
                    "col_count": s.col_count,
                    "merged_ranges": s.merged_ranges,
                }
                if include_data:
                    item["data"] = s.data
                sheets.append(item)
            return sheets

    async def get_clauses(self, document_id: UUID) -> list[dict]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(Clause)
                .where(Clause.document_id == document_id)
                .order_by(Clause.source_page, Clause.source_sheet, Clause.clause_number)
            )
            return [
                {
                    "id": str(c.id),
                    "section": c.section,
                    "clause_number": c.clause_number,
                    "title": c.title,
                    "raw_text": c.raw_text,
                    "category": c.category,
                    "source_page": c.source_page,
                    "source_sheet": c.source_sheet,
                    "source_range": c.source_range,
                }
                for c in result.scalars().all()
            ]


extraction_service = ExtractionService()
