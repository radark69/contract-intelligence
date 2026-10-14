import re
from dataclasses import dataclass

from app.extraction.pdf import PageResult
from app.extraction.xlsx import SheetResult

TOP_HEADING_RE = re.compile(r"^\s*(\d{1,2})\.\s+([A-Z][A-Za-z0-9&,\-/'() ]{1,95})\s*$")
ARTICLE_RE = re.compile(
    r"^\s*(?:ARTICLE|CLAUSE|SECTION)\s+(\d+(?:\.\d+)*)\s*[.\-–—:]?\s*(.*)$",
    re.IGNORECASE,
)
SUBCLAUSE_RE = re.compile(r"^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})*)\s+(\S.*)$")
CAPS_HEADING_RE = re.compile(
    r"^\s*((?:SCHEDULE|ANNEXURE|ANNEX|APPENDIX|EXHIBIT)\b.*)$", re.IGNORECASE
)
LABEL_ROW_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[.\-–—]?\s+(.*)$")

MAX_HEADING_WORDS = 14


@dataclass
class ClauseDraft:
    section: str | None
    clause_number: str | None
    title: str | None
    raw_text: str
    source_page: int | None = None
    source_sheet: str | None = None
    source_range: str | None = None


def _is_heading_line(rest: str) -> bool:
    words = rest.split()
    if not 1 <= len(words) <= MAX_HEADING_WORDS:
        return False
    if rest.rstrip().endswith((".", ";", ",")):
        return False
    return True


def segment_pdf_pages(pages: list[PageResult]) -> list[ClauseDraft]:
    """Split extracted PDF page text into clause drafts with page references."""
    drafts: list[ClauseDraft] = []
    current: ClauseDraft | None = None
    current_lines: list[str] = []
    last_section: str | None = None

    def flush() -> None:
        nonlocal current, current_lines
        if current is not None:
            text = "\n".join(current_lines).strip()
            if text or current.title:
                current.raw_text = text
                drafts.append(current)
        current = None
        current_lines = []

    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                if current_lines:
                    current_lines.append("")
                continue

            m = TOP_HEADING_RE.match(stripped)
            if m and _is_heading_line(m.group(2)):
                flush()
                last_section = m.group(2).strip()
                current = ClauseDraft(
                    section=last_section,
                    clause_number=m.group(1),
                    title=last_section,
                    raw_text="",
                    source_page=page.page_number,
                )
                continue

            m = ARTICLE_RE.match(stripped)
            if m:
                title = m.group(2).strip() or None
                flush()
                last_section = title or last_section
                current = ClauseDraft(
                    section=last_section,
                    clause_number=m.group(1),
                    title=title,
                    raw_text="",
                    source_page=page.page_number,
                )
                continue

            m = CAPS_HEADING_RE.match(stripped)
            if m:
                flush()
                heading = m.group(1).strip()
                last_section = heading
                current = ClauseDraft(
                    section=heading,
                    clause_number=None,
                    title=heading,
                    raw_text="",
                    source_page=page.page_number,
                )
                continue

            m = SUBCLAUSE_RE.match(stripped)
            if m:
                flush()
                current = ClauseDraft(
                    section=last_section,
                    clause_number=m.group(1),
                    title=None,
                    raw_text="",
                    source_page=page.page_number,
                )
                current_lines = [m.group(2)]
                continue

            if current is None:
                current = ClauseDraft(
                    section=last_section,
                    clause_number=None,
                    title=None,
                    raw_text="",
                    source_page=page.page_number,
                )
            current_lines.append(stripped)

    flush()
    return drafts


def segment_xlsx_sheets(sheets: list[SheetResult]) -> list[ClauseDraft]:
    """Turn non-empty spreadsheet rows into clause drafts with sheet/range references."""
    drafts: list[ClauseDraft] = []
    for sheet in sheets:
        for row in sheet.data:
            cells = row["cells"]
            texts = [str(c["value"]) for c in cells if c["value"] not in (None, "")]
            if not texts:
                continue
            row_text = " | ".join(texts)
            first = texts[0]

            clause_number = None
            title = None
            m = LABEL_ROW_RE.match(first)
            if m:
                clause_number = m.group(1)
                title = m.group(2).strip()[:255] or None
            elif len(first) <= 120 and not first.endswith((".", ";")):
                title = first

            drafts.append(
                ClauseDraft(
                    section=sheet.sheet_name,
                    clause_number=clause_number,
                    title=title,
                    raw_text=row_text,
                    source_sheet=sheet.sheet_name,
                    source_range=row["range"],
                )
            )
    return drafts
