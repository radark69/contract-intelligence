import enum
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


class DocumentStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    ANALYZED = "analyzed"
    REPORTED = "reported"
    FAILED = "failed"


class DocumentType(enum.StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"
    XLS = "xls"


class FindingSeverity(enum.StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class FindingCategory(enum.StrEnum):
    COMMERCIAL = "commercial"
    OPERATIONAL = "operational"
    HSE = "hse"
    LEGAL = "legal"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    SCOPE = "scope"
    SCHEDULE = "schedule"
    DATA = "data"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False
    )
    client: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contractor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    contract_value: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    clauses: Mapped[list["Clause"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    obligations: Mapped[list["Obligation"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    economic_exposures: Mapped[list["EconomicExposure"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    facts: Mapped[list["ContractFact"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )
    sheets: Mapped[list["DocumentSheet"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentSheet.position"
    )
    tables: Mapped[list["ExtractedTable"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_ocr: Mapped[bool] = mapped_column(default=False, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="pages")


class DocumentSheet(Base):
    __tablename__ = "document_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_hidden: Mapped[bool] = mapped_column(default=False, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    col_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_ranges: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    data: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="sheets")


class ExtractedTable(Base):
    __tablename__ = "extracted_tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_sheet: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="tables")


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clause_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_sheet: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="clauses")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="clause", cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[FindingCategory] = mapped_column(Enum(FindingCategory), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(Enum(FindingSeverity), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    finding: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    dbs_policy_rule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    interpreted_obligation: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_impact: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="findings")
    clause: Mapped[Optional["Clause"]] = relationship(back_populates="findings")


class Obligation(Base):
    __tablename__ = "obligations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    party: Mapped[str] = mapped_column(String(100), nullable=False)
    obligation: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    required_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    consequence: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="obligations")


class EconomicExposure(Base):
    __tablename__ = "economic_exposures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    scenario: Mapped[str] = mapped_column(String(100), nullable=False)
    assumption: Mapped[str] = mapped_column(Text, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="economic_exposures")


class ContractFact(Base):
    __tablename__ = "contract_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict | list | str | float | bool | None] = mapped_column(JSON, nullable=True)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="facts")


Index("ix_documents_status_created", Document.status, Document.created_at)
Index("ix_findings_doc_severity", Finding.document_id, Finding.severity)
Index("ix_clauses_doc_number", Clause.document_id, Clause.clause_number)
Index("ix_pages_doc_page", DocumentPage.document_id, DocumentPage.page_number)
Index("ix_sheets_doc_position", DocumentSheet.document_id, DocumentSheet.position)
Index("ix_facts_doc_key", ContractFact.document_id, ContractFact.key)
