"""Deterministic patterns and normalizers for contract fact extraction.

All parsing here is regex/rule based — no LLM arithmetic (plan section 10).
"""

import re
from datetime import date, datetime
from typing import Any

from dateutil.parser import parse as dateutil_parse

ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fourty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

WORD_NUM_PATTERN = (
    r"(?:\d{1,4}|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fourty|fifty|sixty|seventy|eighty|ninety)(?:[-\s](?:one|two|three|four|"
    r"five|six|seven|eight|nine))?"
)

_CURRENCY_BEFORE = r"(?:USD|US\$|\$|EUR|€|GBP|£|NGN|₦|CAD|C\$|AUD|A\$)"
_CURRENCY_AFTER = (
    r"(?:USD|EUR|GBP|NGN|US\s+Dollars|United\s+States\s+Dollars|Naira|Euros|"
    r"Pounds(?:\s+Sterling)?)"
)
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_SUFFIX = r"(?:[kKmMbB](?![a-zA-Z])|million|billion|thousand)"

MONEY_RE = re.compile(
    rf"(?P<pre>{_CURRENCY_BEFORE})?\s*(?P<num>{_NUM})\s*(?P<suf>{_SUFFIX})?"
    rf"(?:\s*(?P<post>{_CURRENCY_AFTER}))?",
    re.IGNORECASE,
)

CURRENCY_MAP = {
    "USD": "USD",
    "US$": "USD",
    "$": "USD",
    "US DOLLARS": "USD",
    "UNITED STATES DOLLARS": "USD",
    "EUR": "EUR",
    "€": "EUR",
    "EUROS": "EUR",
    "GBP": "GBP",
    "£": "GBP",
    "POUNDS": "GBP",
    "POUNDS STERLING": "GBP",
    "NGN": "NGN",
    "₦": "NGN",
    "NAIRA": "NGN",
    "CAD": "CAD",
    "C$": "CAD",
    "AUD": "AUD",
    "A$": "AUD",
}
SUFFIX_MULTIPLIER = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

DATE_ALTERNATION = (
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|"
    r"Sep|Sept|Oct|Nov|Dec)\s+\d{4}"
    r"|(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
    r"|\d{1,2}/\d{1,2}/\d{4}"
)

DATE_RE = re.compile(rf"(?P<date>{DATE_ALTERNATION})", re.IGNORECASE)

DATE_LABEL_RE = re.compile(
    r"(?P<label>effective\s+date|commencement\s+date|commence(?:ment)?|start\s+date|"
    r"expiry\s+date|expiration\s+date|expire|end\s+date|termination\s+date|"
    r"date\s+of\s+(?:commencement|expiry|expiration|termination)|initial\s+term)"
    r"[^.\n]{0,40}?(?P<date>" + DATE_ALTERNATION + ")",
    re.IGNORECASE,
)

EXPIRY_LABELS = ("expiry", "expire", "expiration", "end date", "termination")

DURATION_RE = re.compile(
    rf"(?:(?P<w>{WORD_NUM_PATTERN})\s*(?:\(\s*(?P<wp>\d+)\s*\))?"
    rf"|(?P<n>\d{1, 4}))\s*(?:\(\s*(?P<np>\d+)\s*\))?\s*"
    rf"(?P<unit>months?|years?|weeks?|days?)\b",
    re.IGNORECASE,
)

PAYMENT_RE = re.compile(
    rf"(?:"
    rf"(?:payment\s+terms?|terms?\s+of\s+payment|invoice\s+approval)\s*"
    rf"(?:shall\s+be|is|:|of|=|are)?\s*(?:within\s+)?"
    rf"(?P<d>{WORD_NUM_PATTERN})\s*(?:\(\s*\d+\s*\))?\s*days?"
    rf"|net\s+(?P<net>\d{{1,3}})\s*days?"
    rf"|within\s+(?P<within>\d{{1,3}})\s*(?:\(\s*\d+\s*\))?\s*days?\s+of\s+"
    rf"(?:invoice|receipt|submission|approval|valid invoice)"
    rf"|(?:invoice|payment)\s+(?:shall\s+be\s+)?(?:made\s+)?(?:within\s+)?"
    rf"(?P<inv>\d{{1,3}})\s*days?"
    rf")",
    re.IGNORECASE,
)

RATE_RE = re.compile(
    rf"(?P<kind>day|daily|night|standby|stand-by|hire)\s*[-\s]?rate"
    rf"[^.\n]{{0,30}}?(?:of\s+)?(?P<pre>{_CURRENCY_BEFORE})?\s*"
    rf"(?P<num>{_NUM})\s*(?P<suf>{_SUFFIX})?(?:\s*(?P<post>{_CURRENCY_AFTER}))?",
    re.IGNORECASE,
)

AVAILABILITY_RE = re.compile(
    r"(?P<pct1>\d{1,2}(?:\.\d+)?)\s*%\s*(?:contract\s+)?(?:availability|uptime|"
    r"utilisation|utilization)"
    r"|availability\s+(?:of|shall\s+be|guarantee(?:d)?|target|requirement)?\s*"
    r"(?P<pct2>\d{1,2}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

LD_RE = re.compile(
    rf"(?:liquidated\s+damages?|\bLDs?\b)[^.\n]{{0,120}}?"
    rf"(?P<pre>{_CURRENCY_BEFORE})?\s*(?P<num>{_NUM})\s*(?P<suf>{_SUFFIX})?"
    rf"(?:\s*(?P<post>{_CURRENCY_AFTER}))?\s*(?:per|/|each|-)\s*"
    rf"(?P<per>day|hour|week|month|day\s+of\s+delay)",
    re.IGNORECASE,
)

LD_PERCENT_RE = re.compile(
    r"(?:liquidated\s+damages?|\bLDs?\b)[^.\n]{0,120}?"
    r"(?P<pct>\d{1,2}(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:the\s+)?(?:contract\s+value|"
    r"contract\s+price|total\s+value)\s*(?:per|each|for\s+each)\s*"
    r"(?P<per>day|week|month)",
    re.IGNORECASE,
)

UNLIMITED_LIABILITY_RE = re.compile(
    r"(?:(?:liability|liabilities)\s+(?:shall\s+be\s+)?unlimited"
    r"|unlimited\s+(?:liability|liabilities)"
    r"|uncapped\s+(?:liability|liabilities)"
    r"|liability\s+(?:shall\s+be|is|remains)\s+uncapped)",
    re.IGNORECASE,
)

LIABILITY_CAP_RE = re.compile(
    rf"(?:liability|liabilities)[^.\n]{{0,60}}?"
    rf"(?:shall\s+(?:not\s+exceed|be\s+(?:limited|capped))|capped\s+at|limited\s+to|"
    rf"not\s+exceed(?:ing)?|maximum\s+(?:of|liability))"
    rf"[^.\n]{{0,30}}?(?:of\s+)?(?P<pre>{_CURRENCY_BEFORE})?\s*"
    rf"(?P<num>{_NUM})\s*(?P<suf>{_SUFFIX})?(?:\s*(?P<post>{_CURRENCY_AFTER}))?",
    re.IGNORECASE,
)

TERMINATION_NOTICE_RE = re.compile(
    rf"(?:terminat\w+|suspend\w+)[^.\n]{{0,150}}?"
    rf"(?P<n>{WORD_NUM_PATTERN})\s*(?:\(\s*\d+\s*\))?\s*days?\s*(?:written\s+)?notice"
    rf"|notice\s+of\s+(?P<n2>\d{{1,3}})\s*days\s+(?:written\s+)?(?:notice\s+)?"
    rf"(?:of\s+)?(?:termination|to\s+terminate|to\s+suspend)",
    re.IGNORECASE,
)

ESCALATION_RE = re.compile(
    r"(?:escalation|escalate\w+|annual\s+escalation)[^.\n]{0,60}?"
    r"(?P<pct>\d{1,2}(?:\.\d+)?)\s*(?:%|percent)",
    re.IGNORECASE,
)

PCT_LABEL_RE = re.compile(
    r"(?P<pct>\d{1,2}(?:\.\d+)?)\s*%\s*(?:of\s+)?"
    r"(?P<label>withholding\s+tax|tax\s+withheld|retention|retentions|"
    r"local\s+content|nigerian\s+content|ncdmb)"
    r"|(?P<label2>withholding\s+tax|retention|retention\s+money|local\s+content|"
    r"nigerian\s+content)\s*(?:of|at|:)?\s*(?P<pct2>\d{1,2}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

CLIENT_RE = re.compile(
    r"(?:^|\n)\s*(?:Client|Customer)\s*[:\u2013\u2014-]\s*(?P<name>[A-Z][^,\n]{2,70})",
    re.IGNORECASE,
)
CONTRACTOR_RE = re.compile(
    r"(?:^|\n)\s*(?:Contractor|Service Provider|Supplier)\s*[:\u2013\u2014-]\s*"
    r"(?P<name>[A-Z][^,\n]{2,70})",
    re.IGNORECASE,
)


def word_to_int(text: str) -> int | None:
    text = text.strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total = 0
    current = 0
    for part in re.split(r"[-\s]+", text):
        if part in ONES:
            current += ONES[part]
        elif part in TENS:
            current += TENS[part]
        elif part == "hundred":
            current = (current or 1) * 100
        else:
            return None
    return total + current


def normalize_currency(raw: str) -> str | None:
    return CURRENCY_MAP.get(raw.strip().upper())


def parse_money(match: re.Match, *, unmarked_ok: bool = False) -> tuple[float, str | None] | None:
    """Parse a money regex match into (amount, currency).

    Requires a currency marker, a thousands separator, or a k/m/b suffix —
    otherwise it is just an ordinary number (e.g. "36 months").
    Callers in explicit label contexts (e.g. "Contract Value:") may pass
    unmarked_ok=True to accept plain numbers.
    """
    num = match.group("num")
    if not num:
        return None
    pre = match.groupdict().get("pre")
    post = match.groupdict().get("post")
    suf = match.groupdict().get("suf")
    has_separator = "," in num
    marked = bool(pre or post or suf or has_separator)

    if not marked and not unmarked_ok:
        return None

    amount = float(num.replace(",", "").replace(" ", ""))
    if suf:
        multiplier = SUFFIX_MULTIPLIER.get(suf.lower().rstrip("."))
        if multiplier:
            amount *= multiplier

    currency = None
    if pre:
        currency = normalize_currency(pre)
    elif post:
        currency = normalize_currency(post)
    return amount, currency


def parse_date(raw: str) -> str | None:
    """Parse a date string to ISO format. Slash dates use day-first (NG/UK convention)."""
    raw = raw.strip()
    cleaned = re.sub(r"(\d{1,2})(?:st|nd|rd|th)", r"\1", raw, flags=re.IGNORECASE)

    for fmt in (
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue

    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", cleaned):
        try:
            parsed = dateutil_parse(cleaned, dayfirst=True, fuzzy=False)
            if parsed.year > 2100 or parsed.year < 1900:
                return None
            return str(parsed.date().isoformat())
        except (ValueError, OverflowError):
            return None
    return None


def duration_to_months(count: int, unit: str) -> int:
    unit = unit.lower()
    if unit.startswith("year"):
        return count * 12
    if unit.startswith("week"):
        return round(count * 7 / 30.44)
    if unit.startswith("day"):
        return round(count / 30.44)
    return count


def duration_raw(w: str | None, wp: str | None, n: str | None, np_: str | None, unit: str) -> str:
    if w and wp:
        return f"{w} ({wp}) {unit}"
    if n and np_:
        return f"{n} ({np_}) {unit}"
    if w:
        return f"{w} {unit}"
    return f"{n} {unit}"


def is_iso_date(value: Any) -> bool:
    return isinstance(value, str) and bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value))


def today() -> date:
    return date.today()
