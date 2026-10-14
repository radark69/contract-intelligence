"""Deterministic obligation extraction (plan: obligation matrix).

Sentence-level rule extraction: party + mandatory verb + action, with
trigger and frequency detection. No LLM required; the LLM client can
enrich results later without changing persistence.
"""

import re
from dataclasses import dataclass
from uuid import UUID

from app.storage.models import Clause

OBLIGATION_RE = re.compile(
    r"(?P<pre>[^.\n]{0,120}?)"
    r"(?P<verb>shall|must|is required to|are required to|agrees to|undertakes to|will)\s+"
    r"(?P<action>[^.\n]{1,200})",
    re.IGNORECASE,
)

TRIGGER_RE = re.compile(
    r"\b(?:upon|after|within|following|prior to|before|when|once|in the event of)\s+"
    r"([^,.;]{3,60})",
    re.IGNORECASE,
)

FREQUENCY_RE = re.compile(
    r"\b(?:daily|weekly|monthly|quarterly|annually|per day|per month|per annum|"
    r"each day|on an ongoing basis|continuously|as required)\b",
    re.IGNORECASE,
)

PARTY_PATTERNS = [
    ("Contractor", re.compile(r"contractor|service provider|dbs", re.IGNORECASE)),
    ("Client", re.compile(r"client|company|employer|owner", re.IGNORECASE)),
]


@dataclass
class ExtractedObligation:
    party: str
    obligation: str
    trigger: str | None
    frequency: str | None
    source_reference: str
    clause_id: UUID | None
    confidence: float


def _detect_party(prefix: str) -> str:
    for party, pattern in PARTY_PATTERNS:
        if pattern.search(prefix):
            return party
    return "Both"


def _source_reference(clause: Clause) -> str:
    if clause.source_page is not None:
        return f"Page {clause.source_page} → Clause {clause.clause_number or '?'}"
    if clause.source_sheet:
        rng = clause.source_range or ""
        return f"Sheet: {clause.source_sheet}" + (f" Range: {rng}" if rng else "")
    return f"Clause {clause.clause_number or '?'}"


def extract_from_clause(clause: Clause) -> list[ExtractedObligation]:
    out: list[ExtractedObligation] = []
    text = clause.raw_text or ""
    for m in OBLIGATION_RE.finditer(text):
        pre, action = m.group("pre").strip(), m.group("action").strip()
        # Party must be resolvable from the immediate prefix.
        party = _detect_party(pre[-80:]) if pre else "Both"
        if not pre or party == "Both":
            continue
        action = re.sub(r"\s+", " ", action)
        if len(action) < 8:
            continue

        trigger_m = TRIGGER_RE.search(m.group(0))
        freq_m = FREQUENCY_RE.search(m.group(0))
        out.append(
            ExtractedObligation(
                party=party,
                obligation=action.rstrip(" ,"),
                trigger=trigger_m.group(1).strip() if trigger_m else None,
                frequency=freq_m.group(0).lower() if freq_m else None,
                source_reference=_source_reference(clause),
                clause_id=clause.id,
                confidence=0.8 if party != "Both" else 0.65,
            )
        )
    return out


def extract_obligations(clauses: list[Clause]) -> list[ExtractedObligation]:
    results: list[ExtractedObligation] = []
    seen: set[tuple[str, str]] = set()
    for clause in clauses:
        for ob in extract_from_clause(clause):
            key = (ob.party, ob.obligation.lower())
            if key in seen:
                continue
            seen.add(key)
            results.append(ob)
    return results
