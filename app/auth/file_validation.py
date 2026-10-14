"""Malicious file detection and validation."""

import magic
from dataclasses import dataclass

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

DANGEROUS_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".sh", ".bat", ".cmd", ".ps1",
    ".py", ".js", ".jar", ".class", ".php", ".rb", ".pl",
    ".html", ".htm", ".svg", ".xml",
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

PDF_MAGIC = b"%PDF"
XLSX_MAGIC = b"PK\x03\x04"  # ZIP-based (xlsx)


@dataclass
class FileValidationResult:
    valid: bool
    mime_type: str | None
    error: str | None
    warnings: list[str]


def validate_file_content(file_bytes: bytes, filename: str) -> FileValidationResult:
    """
    Validate uploaded file content against allowed types and malicious patterns.
    Uses python-magic for MIME detection (content-based, not extension-based).
    """
    warnings = []

    # Size check
    if len(file_bytes) > MAX_FILE_SIZE:
        return FileValidationResult(
            valid=False,
            mime_type=None,
            error=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)} MB",
            warnings=warnings,
        )

    # Extension check
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if f".{ext}" in DANGEROUS_EXTENSIONS:
        return FileValidationResult(
            valid=False,
            mime_type=None,
            error=f"Dangerous file extension: .{ext}",
            warnings=warnings,
        )

    # MIME type detection via magic bytes
    mime = magic.from_buffer(file_bytes, mime=True)

    if mime not in ALLOWED_MIME_TYPES:
        return FileValidationResult(
            valid=False,
            mime_type=mime,
            error=f"Unsupported file type: {mime}. Allowed: PDF, XLSX",
            warnings=warnings,
        )

    # Additional content validation
    if mime == "application/pdf":
        if not file_bytes.startswith(PDF_MAGIC):
            warnings.append("PDF magic bytes missing - may be corrupted")
    elif mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        if not file_bytes.startswith(XLSX_MAGIC):
            warnings.append("XLSX magic bytes missing - may be corrupted")
        # Check for embedded macros (XLSB would be different magic)
        if b"xl/vbaProject.bin" in file_bytes:
            warnings.append("File contains VBA macros - will be ignored during extraction")

    return FileValidationResult(valid=True, mime_type=mime, error=None, warnings=warnings)


def is_safe_filename(filename: str) -> bool:
    """Basic filename safety - no path traversal, no null bytes, reasonable length."""
    if not filename or len(filename) > 255:
        return False
    if "\x00" in filename or ".." in filename or "/" in filename or "\\" in filename:
        return False
    return True