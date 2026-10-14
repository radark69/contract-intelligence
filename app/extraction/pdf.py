import logging
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

OCR_MIN_CHARS = 100
OCR_DPI = 300


@dataclass
class PageResult:
    page_number: int
    text: str
    is_ocr: bool = False
    table_count: int = 0
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class PdfExtractionResult:
    pages: list[PageResult]
    warnings: list[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class PdfExtractor:
    """Extract text, tables, and (as fallback) OCR'd text from PDF files."""

    def __init__(self, ocr_languages: str = "eng", tesseract_path: str | None = None):
        self.ocr_languages = ocr_languages
        self.tesseract_path = tesseract_path
        self._ocr_available: bool | None = None

    def _ocr_available_check(self) -> bool:
        if self._ocr_available is not None:
            return self._ocr_available
        try:
            import pytesseract  # type: ignore[import-untyped]

            if self.tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            pytesseract.get_tesseract_version()
            self._ocr_available = True
        except Exception:
            self._ocr_available = False
        return self._ocr_available

    def _ocr_page(self, pdf_path: Path, page_index: int) -> str:
        import pymupdf
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image

        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        with pymupdf.open(pdf_path) as doc:
            page = doc[page_index]
            pix = page.get_pixmap(dpi=OCR_DPI)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return str(pytesseract.image_to_string(img, lang=self.ocr_languages))

    def extract(self, pdf_path: Path) -> PdfExtractionResult:
        warnings: list[str] = []
        pages: list[PageResult] = []
        ocr_used = False

        with pdfplumber.open(pdf_path) as pdf:
            for index, page in enumerate(pdf.pages):
                page_number = index + 1
                text = page.extract_text() or ""
                raw_tables = page.extract_tables() or []
                tables = [
                    [[cell if cell is not None else "" for cell in row] for row in table]
                    for table in raw_tables
                ]

                is_ocr = False
                if len(text.strip()) < OCR_MIN_CHARS:
                    if self._ocr_available_check():
                        try:
                            ocr_text = self._ocr_page(pdf_path, index)
                            if len(ocr_text.strip()) > len(text.strip()):
                                text = ocr_text
                                is_ocr = True
                                ocr_used = True
                        except Exception as exc:
                            logger.warning("OCR failed on page %d: %s", page_number, exc)
                            warnings.append(
                                f"OCR failed on page {page_number}: {exc.__class__.__name__}"
                            )
                    else:
                        if page_number == 1:
                            warnings.append(
                                "Scanned/low-text PDF detected but OCR (tesseract) is not "
                                "installed — some pages may have no extractable text"
                            )

                pages.append(
                    PageResult(
                        page_number=page_number,
                        text=text,
                        is_ocr=is_ocr,
                        table_count=len(tables),
                        tables=tables,
                    )
                )

        if ocr_used:
            warnings.append("OCR fallback used on one or more pages (scanned content)")
        return PdfExtractionResult(pages=pages, warnings=warnings)
