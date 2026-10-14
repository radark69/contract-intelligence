CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("indemnity", ["indemnit"]),
    ("liability", ["liabilit", "limitation of liability", "uncapped"]),
    ("liquidated_damages", ["liquidated damage", "ld rate", "penalty", "penalties"]),
    ("termination", ["termination", "terminate", "for convenience", "expiry"]),
    ("suspension", ["suspension", "suspend"]),
    ("insurance", ["insurance", "insurer", "policy limit"]),
    (
        "hse",
        [
            "hse",
            "health and safety",
            "occupational",
            "incident",
            "permit to work",
            "ptw",
            "simops",
            "environment",
            "emission",
            "spill",
            "stop-work",
            "stop work",
        ],
    ),
    ("confidentiality", ["confidential", "non-disclosure", "non disclosure"]),
    ("intellectual_property", ["intellectual property", "copyright", "proprietary"]),
    ("data_protection", ["data protection", "personal data", "gdpr", "data privacy"]),
    ("audit", ["audit", "auditor"]),
    (
        "dispute_resolution",
        [
            "dispute",
            "arbitration",
            "governing law",
            "governed by",
            "jurisdiction",
            "venue",
        ],
    ),
    ("force_majeure", ["force majeure"]),
    (
        "regulatory",
        [
            "regulat",
            "compliance",
            "nuprc",
            "ncdmb",
            "nigerian content",
            "local content",
            "statutory",
        ],
    ),
    (
        "payment",
        [
            "payment",
            "invoice",
            "invoic",
            "remuneration",
            "day rate",
            "standby rate",
            "retention",
            "set-off",
            "setoff",
            "deduction",
        ],
    ),
    ("taxes", ["tax", "withholding", "vat", "value added tax"]),
    ("currency_fx", ["currency", "foreign exchange", "fx", "usd", "naira", "exchange rate"]),
    (
        "pricing",
        ["contract value", "price", "pricing", "escalation", "adjustment of price", "reimbursable"],
    ),
    ("mobilisation", ["mobilis", "mobiliz"]),
    ("demobilisation", ["demobilis", "demobiliz"]),
    ("availability", ["availability", "uptime", "utilisation", "utilization"]),
    ("downtime_npt", ["downtime", "non-productive", "npt", "deferment", "offline"]),
    ("kpi", ["kpi", "key performance", "performance indicator", "service level"]),
    ("maintenance", ["maintenance", "preventive", "corrective", "spare part", "overhaul"]),
    ("scope", ["scope of work", "scope", "exclusion", "deliverable", "obligation of"]),
    ("personnel", ["personnel", "manning", "competency", "competence", "training", "visa"]),
    ("procurement", ["procurement", "subcontractor", "sub-contractor", "purchase order"]),
    ("change_control", ["change order", "change control", "variation", "change request"]),
    ("claims", ["claim", "claims"]),
    ("renewal", ["renewal", "renew", "extension of term"]),
    ("assignment", ["assignment", "assign "]),
    ("subcontracting", ["subcontract", "sub-contract"]),
    ("warranties", ["warrant", "representation"]),
]

GENERAL_CATEGORY = "general"


def classify_clause(title: str | None, raw_text: str) -> str:
    """Deterministic keyword classification against the plan's clause taxonomy."""
    haystack = f"{title or ''}\n{raw_text}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in haystack:
                return category
    return GENERAL_CATEGORY


def source_reference(
    page: int | None = None, sheet: str | None = None, cell_range: str | None = None
) -> str:
    if sheet:
        ref = f"Sheet: {sheet}"
        if cell_range:
            ref += f", Range: {cell_range}"
        return ref
    if page is not None:
        return f"Page {page}"
    return "Unknown source"
