"""Report generation orchestration (plan checklist: report generation)."""

import logging
from uuid import UUID

from app.reports.data import ReviewData, load_review_data
from app.reports.docx_report import build_docx
from app.reports.pdf_report import build_pdf
from app.reports.xlsx_register import build_xlsx

logger = logging.getLogger(__name__)


class ReportService:
    async def generate(self, document_id: UUID, fmt: str) -> tuple[bytes, str, str]:
        """Return (payload, media_type, filename) for docx | pdf | xlsx."""
        data: ReviewData = await load_review_data(document_id)
        stem = data.document.filename.rsplit(".", 1)[0]
        if fmt == "docx":
            payload = build_docx(data)
            return (
                payload,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                f"{stem}_Contract_Review.docx",
            )
        if fmt == "pdf":
            return build_pdf(data), "application/pdf", f"{stem}_Contract_Review.pdf"
        if fmt == "xlsx":
            return (
                build_xlsx(data),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{stem}_Risk_Register.xlsx",
            )
        raise ValueError(f"unsupported report format: {fmt}")


report_service = ReportService()
