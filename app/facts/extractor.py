"""Span-based deterministic fact extraction.

Each rule scans a text span and yields FactCandidates with normalized values,
confidence, and source references. Rules run in priority order per span;
candidates are deduplicated per (key, value) across the document by the service.
"""

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.facts.patterns import (
    AVAILABILITY_RE,
    CLIENT_RE,
    CONTRACTOR_RE,
    DATE_LABEL_RE,
    DURATION_RE,
    ESCALATION_RE,
    LD_PERCENT_RE,
    LD_RE,
    LIABILITY_CAP_RE,
    MONEY_RE,
    PAYMENT_RE,
    PCT_LABEL_RE,
    RATE_RE,
    TERMINATION_NOTICE_RE,
    UNLIMITED_LIABILITY_RE,
    duration_raw,
    duration_to_months,
    parse_date,
    parse_money,
    word_to_int,
)

FACT_LABELS: dict[str, str] = {
    "contract_value": "Contract Value",
    "currency": "Currency",
    "start_date": "Effective Date",
    "end_date": "Expiry Date",
    "duration": "Contract Duration",
    "payment_terms_days": "Payment Terms (days)",
    "day_rate": "Day Rate",
    "standby_rate": "Standby Rate",
    "availability_target": "Availability Requirement",
    "ld_rate": "Liquidated Damages Rate",
    "liability_cap": "Liability Cap",
    "unlimited_liability": "Unlimited Liability",
    "termination_notice_days": "Termination Notice Period (days)",
    "escalation_pct": "Escalation Rate (%)",
    "withholding_tax_pct": "Withholding Tax (%)",
    "retention_pct": "Retention (%)",
    "nigerian_content_pct": "Nigerian Content (%)",
    "client": "Client",
    "contractor": "Contractor",
}

DURATION_STOP_RE = re.compile(
    r"invoice|payment|notice|cure|approval|receipt|net\s|deduction|advance",
    re.IGNORECASE,
)

PCT_LABEL_KEYS = {
    "withholding tax": "withholding_tax_pct",
    "tax withheld": "withholding_tax_pct",
    "retention": "retention_pct",
    "retentions": "retention_pct",
    "retention money": "retention_pct",
    "local content": "nigerian_content_pct",
    "nigerian content": "nigerian_content_pct",
    "ncdmb": "nigerian_content_pct",
}


@dataclass
class TextSpan:
    text: str
    source_reference: str
    clause_id: UUID | None = None


@dataclass
class FactCandidate:
    key: str
    value: Any
    raw_value: str
    confidence: float
    source_reference: str
    source_text: str
    clause_id: UUID | None = None


def _context(text: str, start: int, end: int, radius: int = 150) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return text[lo:hi].replace("\n", " ").strip()


def extract_from_span(span: TextSpan) -> list[FactCandidate]:
    found: list[FactCandidate] = []
    text = span.text

    def add(key: str, value: Any, raw: str, confidence: float, match: re.Match) -> None:
        found.append(
            FactCandidate(
                key=key,
                value=value,
                raw_value=raw,
                confidence=confidence,
                source_reference=span.source_reference,
                source_text=_context(text, match.start(), match.end()),
                clause_id=span.clause_id,
            )
        )

    # --- Contract value (labeled) ---
    for m in re.finditer(
        r"(?:total\s+)?(?:contract\s+(?:value|sum|price|amount)|agreement\s+value|"
        r"total\s+(?:value|price|consideration)|contract\s+price)\s*"
        r"(?:is|of|:|=|amounting\s+to|shall\s+be)?\s*",
        text,
        re.IGNORECASE,
    ):
        tail = text[m.end() : m.end() + 80]
        money_match = MONEY_RE.match(tail)
        if not money_match:
            continue
        money = parse_money(money_match, unmarked_ok=True)
        if money is None:
            continue
        amount, currency = money
        if currency is None and amount < 1000:
            continue
        add(
            "contract_value",
            {"amount": amount, "currency": currency},
            money_match.group(0).strip(),
            0.92,
            m,
        )

    # --- Dates (label-driven) ---
    for m in DATE_LABEL_RE.finditer(text):
        iso = parse_date(m.group("date"))
        if not iso:
            continue
        label = m.group("label").lower()
        key = (
            "end_date"
            if any(
                x in label for x in ("expiry", "expire", "expiration", "end date", "termination")
            )
            else "start_date"
        )
        add(key, iso, m.group("date"), 0.9, m)

    # --- Duration (skip payment/notice day-counts) ---
    for m in DURATION_RE.finditer(text):
        window = text[max(0, m.start() - 40) : m.end() + 40]
        if DURATION_STOP_RE.search(window):
            continue
        w, wp, n, np_ = m.group("w"), m.group("wp"), m.group("n"), m.group("np")
        count = None
        if w and wp:
            count = int(wp)
        elif w:
            count = word_to_int(w)
        elif n:
            count = int(n)
        if not count or count <= 0 or count > 1200:
            continue
        unit = m.group("unit")
        months = duration_to_months(count, unit)
        if months <= 0:
            continue
        add("duration", {"months": months}, duration_raw(w, wp, n, np_, unit), 0.85, m)

    # --- Payment terms ---
    for m in PAYMENT_RE.finditer(text):
        raw_days = m.group("d") or m.group("net") or m.group("within") or m.group("inv")
        if not raw_days:
            continue
        days = None
        if raw_days.isdigit():
            days = int(raw_days)
        else:
            days = word_to_int(raw_days)
        if not days or days <= 0 or days > 365:
            continue
        add("payment_terms_days", days, m.group(0).strip(), 0.88, m)

    # --- Rates ---
    for m in RATE_RE.finditer(text):
        money = parse_money(m)
        if money is None:
            continue
        amount, currency = money
        kind = m.group("kind").lower()
        key = "standby_rate" if kind in ("standby", "stand-by") else "day_rate"
        add(key, {"amount": amount, "currency": currency}, m.group(0).strip(), 0.87, m)

    # --- Availability ---
    for m in AVAILABILITY_RE.finditer(text):
        pct = m.group("pct1") or m.group("pct2")
        if not pct:
            continue
        value = float(pct)
        if not 0 < value <= 100:
            continue
        add("availability_target", value, f"{value}%", 0.9, m)

    # --- Liquidated damages ---
    for m in LD_RE.finditer(text):
        money = parse_money(m)
        if money is None:
            continue
        amount, currency = money
        per = re.sub(r"\s+", " ", m.group("per").lower().strip())
        add(
            "ld_rate",
            {"amount": amount, "currency": currency, "per": per},
            m.group(0).strip(),
            0.88,
            m,
        )

    for m in LD_PERCENT_RE.finditer(text):
        per = m.group("per").lower()
        add(
            "ld_rate",
            {"percent": float(m.group("pct")), "of": "contract_value", "per": per},
            m.group(0).strip(),
            0.85,
            m,
        )

    # --- Liability ---
    for m in UNLIMITED_LIABILITY_RE.finditer(text):
        add("unlimited_liability", True, m.group(0).strip(), 0.93, m)

    for m in LIABILITY_CAP_RE.finditer(text):
        money = parse_money(m, unmarked_ok=True)
        if money is None:
            continue
        amount, currency = money
        if currency is None and amount < 1000:
            continue
        add("liability_cap", {"amount": amount, "currency": currency}, m.group(0).strip(), 0.88, m)

    # --- Termination / suspension notice ---
    for m in TERMINATION_NOTICE_RE.finditer(text):
        raw_days = m.group("n") or m.group("n2")
        if not raw_days:
            continue
        days = int(raw_days) if raw_days.isdigit() else word_to_int(raw_days)
        if not days or days <= 0 or days > 730:
            continue
        add("termination_notice_days", days, m.group(0).strip(), 0.85, m)

    # --- Escalation ---
    for m in ESCALATION_RE.finditer(text):
        value = float(m.group("pct"))
        if 0 < value <= 100:
            add("escalation_pct", value, f"{value}%", 0.85, m)

    # --- Labeled percentages ---
    for m in PCT_LABEL_RE.finditer(text):
        pct = m.group("pct") or m.group("pct2")
        label = (m.group("label") or m.group("label2") or "").lower()
        if not pct or not label:
            continue
        value = float(pct)
        pct_key = next((k for name, k in PCT_LABEL_KEYS.items() if name in label), None)
        if pct_key and 0 < value <= 100:
            add(pct_key, value, m.group(0).strip(), 0.87, m)

    # --- Parties (explicitly labeled) ---
    for m in CLIENT_RE.finditer(text):
        name = m.group("name").strip().rstrip(".,;")
        if len(name) >= 3:
            add("client", name, m.group(0).strip(), 0.8, m)

    for m in CONTRACTOR_RE.finditer(text):
        name = m.group("name").strip().rstrip(".,;")
        if len(name) >= 3:
            add("contractor", name, m.group(0).strip(), 0.8, m)

    return found


def extract_facts(spans: list[TextSpan]) -> list[FactCandidate]:
    candidates: list[FactCandidate] = []
    seen: set[tuple[str, str]] = set()
    for span in spans:
        for candidate in extract_from_span(span):
            identity = (candidate.key, str(candidate.value))
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append(candidate)
    return candidates
