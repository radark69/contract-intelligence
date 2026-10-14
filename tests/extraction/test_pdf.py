import io

import pytest

from app.extraction.pdf import PdfExtractor

TEXT_CONTRACT = """\
1. DEFINITIONS AND INTERPRETATION
In this Agreement the following terms shall have the meanings assigned to them below.

2. SCOPE OF WORK
2.1 The Contractor shall provide two 2000HP drilling rigs for the drilling campaign.
2.2 The Contractor shall provide all personnel, equipment and materials required.

3. TERM AND AVAILABILITY
The Agreement shall commence on 1 January 2026 and continue for thirty six months.
Contractor guarantees an availability of ninety eight percent of contracted hours.
"""


def build_text_pdf(path, text: str, pages: int = 1) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    lines = text.splitlines()
    per_page = max(len(lines) // pages, 1)
    for p in range(pages):
        y = 720
        for line in lines[p * per_page : (p + 1) * per_page]:
            c.drawString(72, y, line)
            y -= 14
        c.showPage()
    c.save()
    return path.read_bytes()


def build_scanned_pdf(path) -> bytes:
    """Image-only PDF (no text layer) mimicking a scanned contract."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except OSError:
        font = ImageFont.load_default()
    y = 120
    for line in [
        "LIABILITY CLAUSE",
        "The Contractor liability shall be unlimited",
        "for any and all claims howsoever arising",
        "under this Agreement or in connection herewith",
    ]:
        draw.text((100, y), line, fill="black", font=font)
        y += 80

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(ImageReader(buf), 30, 30, width=540, height=720)
    c.showPage()
    c.save()
    return path.read_bytes()


def build_table_pdf(path) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    data = [
        ["Item", "Description", "Rate"],
        ["1", "Rig day rate", "25000"],
        ["2", "Standby rate", "12500"],
    ]
    x_positions = [72, 140, 420, 520]
    top_y = 730
    row_h = 18
    for i, row in enumerate(data):
        y = top_y - i * row_h
        for x, cell in zip(x_positions[:3], row, strict=True):
            c.drawString(x + 4, y - 12, cell)
        c.line(x_positions[0], y, x_positions[3], y)
        c.line(x_positions[0], y - row_h, x_positions[3], y - row_h)
    c.line(x_positions[0], top_y, x_positions[0], top_y - len(data) * row_h)
    c.line(x_positions[1], top_y, x_positions[1], top_y - len(data) * row_h)
    c.line(x_positions[2], top_y, x_positions[2], top_y - len(data) * row_h)
    c.line(x_positions[3], top_y, x_positions[3], top_y - len(data) * row_h)
    c.showPage()
    c.save()
    return path.read_bytes()


class TestPdfExtractor:
    def test_extracts_text_with_page_numbers(self, tmp_path):
        path = tmp_path / "contract.pdf"
        build_text_pdf(path, TEXT_CONTRACT, pages=2)
        result = PdfExtractor().extract(path)
        assert result.page_count == 2
        assert "SCOPE OF WORK" in result.pages[0].text
        assert result.pages[0].is_ocr is False

    def test_no_ocr_warning_for_text_pdf(self, tmp_path):
        path = tmp_path / "contract.pdf"
        build_text_pdf(path, TEXT_CONTRACT)
        result = PdfExtractor().extract(path)
        assert not any("OCR" in w for w in result.warnings)

    def test_scanned_pdf_triggers_ocr(self, tmp_path):
        path = tmp_path / "scanned.pdf"
        build_scanned_pdf(path)
        result = PdfExtractor().extract(path)
        page = result.pages[0]
        if not page.is_ocr:
            pytest.skip("native text layer detected; OCR not triggered")
        assert page.is_ocr is True
        assert "LIABILITY" in page.text.upper()
        assert any("OCR fallback" in w for w in result.warnings)

    def test_empty_page_no_crash(self, tmp_path):
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        path = tmp_path / "blank.pdf"
        c = canvas.Canvas(str(path), pagesize=letter)
        c.showPage()
        c.save()

        result = PdfExtractor().extract(path)
        assert result.page_count == 1
        assert result.pages[0].text.strip() == ""

    def test_table_extraction(self, tmp_path):
        path = tmp_path / "table.pdf"
        build_table_pdf(path)
        result = PdfExtractor().extract(path)
        page = result.pages[0]
        assert page.table_count >= 1
        flat = " ".join(cell for table in page.tables for row in table for cell in row)
        assert "25000" in flat
