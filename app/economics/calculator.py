"""Deterministic financial exposure calculations (plan section 11).

All math is Python — the LLM never computes numbers (plan section 10).
Every exposure carries its explicit formula and a labelled assumption.
When required inputs are missing the result is an honest
'Cannot calculate reliably — missing X' note, never a fabricated number
(plan: do not fabricate assumptions without labelling them).
"""

from dataclasses import dataclass, field

from app.storage.models import ContractFact

DAYS_PER_MONTH = 30.44  # 365.25 / 12
ASSUMED_PAYABLE_DAYS = 30  # labelled assumption for cash-gap only


@dataclass
class ExposureDraft:
    scenario: str
    assumption: str
    formula: str
    result: float
    currency: str
    source_reference: str


@dataclass
class CannotCalculate:
    metric: str
    reason: str


@dataclass
class EconomicsResult:
    exposures: list[ExposureDraft] = field(default_factory=list)
    cannot_calculate: list[CannotCalculate] = field(default_factory=list)


FactValue = dict | list | str | float | bool | None


def _value(facts: dict[str, ContractFact], key: str) -> FactValue:
    f = facts.get(key)
    return None if f is None else f.value


def _amount(facts: dict[str, ContractFact], key: str) -> float | None:
    v = _value(facts, key)
    if isinstance(v, dict):
        v = v.get("amount")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _currency(facts: dict[str, ContractFact]) -> str:
    for key in ("contract_value", "liability_cap", "ld_rate", "day_rate"):
        v = _value(facts, key)
        if isinstance(v, dict) and v.get("currency"):
            return str(v["currency"])
    return "UNSPECIFIED"


def _ref(facts: dict[str, ContractFact], *keys: str) -> str:
    for k in keys:
        f = facts.get(k)
        if f is not None:
            return str(f.source_reference)
    return "document (no single source)"


def _duration_days(facts: dict) -> float | None:
    v = _value(facts, "duration")
    if isinstance(v, dict):
        months = v.get("months")
        if isinstance(months, (int, float)):
            return float(months) * DAYS_PER_MONTH
    return None


def calculate_economics(
    facts: dict[str, ContractFact],
    clause_categories: set[str] | None = None,
) -> EconomicsResult:
    """Compute exposures from extracted facts, gated by available evidence."""
    clause_categories = clause_categories or set()
    out = EconomicsResult()
    currency = _currency(facts)

    revenue = _amount(facts, "contract_value")
    payment_days = _value(facts, "payment_terms_days")
    duration = _duration_days(facts)
    day_rate = _amount(facts, "day_rate")
    ld_rate = _amount(facts, "ld_rate")
    cap = _amount(facts, "liability_cap")

    # --- contract revenue ---------------------------------------------------
    if revenue is not None:
        out.exposures.append(
            ExposureDraft(
                scenario="stated value",
                assumption="Contract value as stated in the document.",
                formula="stated contract value",
                result=revenue,
                currency=currency,
                source_reference=_ref(facts, "contract_value"),
            )
        )
    else:
        out.cannot_calculate.append(CannotCalculate("contract revenue", "missing contract value"))

    # --- revenue from rates (day-rate run-rate) -----------------------------
    if day_rate is not None:
        if duration is not None:
            out.exposures.append(
                ExposureDraft(
                    scenario="day-rate run-rate",
                    assumption=(
                        f"Full term at day rate using {DAYS_PER_MONTH} days/month; "
                        "excludes standby, reimbursables and price variation."
                    ),
                    formula=f"day rate ({day_rate:,.2f}) × months × {DAYS_PER_MONTH}",
                    result=day_rate * duration,
                    currency=currency,
                    source_reference=_ref(facts, "day_rate", "duration"),
                )
            )
        else:
            out.cannot_calculate.append(
                CannotCalculate("day-rate revenue run-rate", "missing contract duration")
            )

    # --- working capital requirement ---------------------------------------
    if revenue is not None and isinstance(payment_days, (int, float)):
        out.exposures.append(
            ExposureDraft(
                scenario="receivables outstanding",
                assumption="Revenue collected after the stated payment term; no early-payment discount.",
                formula=f"revenue ({revenue:,.2f}) × payment days ({payment_days}) / 365",
                result=revenue * float(payment_days) / 365.0,
                currency=currency,
                source_reference=_ref(facts, "contract_value", "payment_terms_days"),
            )
        )
    elif revenue is not None and "payment" in clause_categories:
        out.cannot_calculate.append(
            CannotCalculate("working capital requirement", "missing payment term")
        )

    # --- cash timing gap ----------------------------------------------------
    if revenue is not None and isinstance(payment_days, (int, float)) and duration:
        out.exposures.append(
            ExposureDraft(
                scenario="cost-to-cash timing gap",
                assumption=(
                    f"Labelled assumption: payables to suppliers at net "
                    f"{ASSUMED_PAYABLE_DAYS} days; client pays at {payment_days} days."
                ),
                formula=(
                    f"revenue ({revenue:,.2f}) × max(0, {payment_days} − "
                    f"{ASSUMED_PAYABLE_DAYS}) / 365"
                ),
                result=max(0.0, float(payment_days) - ASSUMED_PAYABLE_DAYS) * revenue / 365.0,
                currency=currency,
                source_reference=_ref(facts, "contract_value", "payment_terms_days"),
            )
        )

    # --- worst-case LD exposure ---------------------------------------------
    if ld_rate is not None:
        per = _value(facts, "ld_rate")
        per_unit = per.get("per", "day") if isinstance(per, dict) else "day"
        if duration is not None:
            out.exposures.append(
                ExposureDraft(
                    scenario="worst case (full-term accrual)",
                    assumption=(
                        "Labelled assumption: LD accrues every day of the term at "
                        "the stated rate; actual exposure requires downtime hours."
                    ),
                    formula=(f"LD rate ({ld_rate:,.2f}/{per_unit}) × term days ({duration:,.0f})"),
                    result=ld_rate * duration,
                    currency=currency,
                    source_reference=_ref(facts, "ld_rate", "duration"),
                )
            )
        else:
            out.cannot_calculate.append(
                CannotCalculate("potential LD exposure", "missing contract duration")
            )
    elif "liquidated_damages" in clause_categories:
        out.cannot_calculate.append(
            CannotCalculate(
                "potential LD exposure",
                "missing LD rate / downtime definition",
            )
        )

    # --- liability cap -------------------------------------------------------
    if cap is not None:
        out.exposures.append(
            ExposureDraft(
                scenario="stated cap",
                assumption="Liability cap as stated in the document.",
                formula="stated liability cap",
                result=cap,
                currency=currency,
                source_reference=_ref(facts, "liability_cap"),
            )
        )

    # --- gross contribution / margin ----------------------------------------
    if revenue is not None:
        out.cannot_calculate.append(
            CannotCalculate(
                "gross contribution and margin",
                "missing estimated direct cost",
            )
        )

    # --- termination exposure ------------------------------------------------
    if "termination" in clause_categories:
        out.cannot_calculate.append(
            CannotCalculate(
                "termination exposure",
                "missing termination fee / cost recovery values",
            )
        )

    # --- downtime revenue exposure ------------------------------------------
    if "availability" in clause_categories or "downtime_npt" in clause_categories:
        out.cannot_calculate.append(
            CannotCalculate(
                "downtime revenue exposure",
                "missing downtime definition / LD rate per hour",
            )
        )

    # --- insurance cost exposure --------------------------------------------
    if "insurance" in clause_categories:
        out.cannot_calculate.append(
            CannotCalculate("insurance cost exposure", "missing premium data")
        )

    # --- mobilisation requirement -------------------------------------------
    if "mobilisation" in clause_categories:
        out.cannot_calculate.append(
            CannotCalculate("mobilisation requirement", "missing mobilisation payment schedule")
        )

    return out
