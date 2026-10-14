"""DBS Contract Playbook rule schema (plan section 6).

The playbook is a structured knowledge base of DBS contract positions.
The AI must never invent DBS policy — every risk finding must reference
a rule defined here (evidence-first, plan section 9).
"""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.storage.models import FindingSeverity


class PlaybookCategory(StrEnum):
    """Playbook rule categories, aligned with the clause taxonomy."""

    COMMERCIAL = "commercial"
    PRICING = "pricing"
    PAYMENT = "payment"
    TAXES = "taxes"
    LIABILITY = "liability"
    INDEMNITY = "indemnity"
    INSURANCE = "insurance"
    LIQUIDATED_DAMAGES = "liquidated_damages"
    TERMINATION = "termination"
    SUSPENSION = "suspension"
    AVAILABILITY = "availability"
    OPERATIONS = "operations"
    HSE = "hse"
    PERSONNEL = "personnel"
    PROCUREMENT = "procurement"
    REGULATORY = "regulatory"
    NIGERIAN_CONTENT = "nigerian_content"
    DISPUTE_RESOLUTION = "dispute_resolution"
    FORCE_MAJEURE = "force_majeure"
    CONFIDENTIALITY = "confidentiality"
    SCOPE = "scope"


class PlaybookRule(BaseModel):
    """A single DBS playbook position.

    Positions (plan section 6):
      preferred  — ideal DBS position
      acceptable — negotiable position
      escalate   — flag for review; explicit criteria required
      reject     — outside DBS policy without management approval
    """

    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*-\d{3}$")
    category: PlaybookCategory
    topic: str = Field(min_length=3, max_length=80)
    severity: FindingSeverity
    requires_management_approval: bool = False

    preferred: str
    acceptable: str
    escalate: str
    reject: str

    clause_categories: list[str] = Field(min_length=1)
    """Clause taxonomy categories this rule is evaluated against."""

    reject_patterns: list[str] = Field(default_factory=list)
    """Regex patterns indicating a 'reject' position (Sprint 5 matching)."""

    escalate_patterns: list[str] = Field(default_factory=list)
    """Regex patterns indicating an 'escalate' position (Sprint 5 matching)."""

    rationale: str = ""

    @model_validator(mode="after")
    def id_prefix_matches_category(self) -> "PlaybookRule":
        prefix = self.id.rsplit("-", 1)[0]
        expected = self.category.upper()
        if prefix != expected:
            raise ValueError(f"rule id prefix '{prefix}' must match category '{expected}'")
        return self

    @field_validator("reject_patterns", "escalate_patterns")
    @classmethod
    def patterns_are_valid_regex(cls, patterns: list[str]) -> list[str]:
        import re

        for p in patterns:
            try:
                re.compile(p, re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"invalid regex {p!r}: {e}") from None
        return patterns

    @field_validator("clause_categories")
    @classmethod
    def clause_categories_known(cls, cats: list[str]) -> list[str]:
        from app.clauses.classifier import CATEGORY_KEYWORDS

        known = {name for name, _ in CATEGORY_KEYWORDS}
        unknown = [c for c in cats if c not in known]
        if unknown:
            raise ValueError(f"unknown clause categories: {sorted(unknown)}")
        return cats


class PlaybookRuleOut(BaseModel):
    """API representation of a playbook rule."""

    id: str
    category: PlaybookCategory
    topic: str
    severity: FindingSeverity
    requires_management_approval: bool
    preferred: str
    acceptable: str
    escalate: str
    reject: str
    clause_categories: list[str]
    rationale: str

    model_config = {"from_attributes": True}
