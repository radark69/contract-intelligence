"""PDF contract review report (plan section 5) — reportlab Platypus."""

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports.data import ReviewData

SEVERITY_COLORS = {
    "critical": colors.HexColor("#B00020"),
    "high": colors.HexColor("#D96C00"),
    "medium": colors.HexColor("#8A6D00"),
    "low": colors.HexColor("#333333"),
    "informational": colors.HexColor("#555555"),
}

HDR_BG = colors.HexColor("#1F3B63")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("RTitle", parent=base["Title"], fontSize=20, textColor=HDR_BG),
        "h1": ParagraphStyle(
            "RH1",
            parent=base["Heading1"],
            fontSize=13,
            textColor=HDR_BG,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "RH2",
            parent=base["Heading2"],
            fontSize=11,
            textColor=HDR_BG,
            spaceBefore=8,
            spaceAfter=3,
        ),
        "body": ParagraphStyle("RBody", parent=base["BodyText"], fontSize=8.5),
        "small": ParagraphStyle("RSmall", parent=base["BodyText"], fontSize=7.5),
        "cell": ParagraphStyle("RCell", parent=base["BodyText"], fontSize=7, leading=9),
        "cellhdr": ParagraphStyle(
            "RCellHdr",
            parent=base["BodyText"],
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        ),
        "bullet": ParagraphStyle("RBullet", parent=base["BodyText"], fontSize=8.5, leftIndent=10),
    }


def _table(
    headers: list[str],
    rows: list[list[str]],
    styles: dict[str, ParagraphStyle],
    col_widths: list[float] | None = None,
) -> Table:
    data = [[Paragraph(h, styles["cellhdr"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), styles["cell"]) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HDR_BG),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFC9D6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return t


def _fact(data: ReviewData, key: str) -> str:
    f = data.facts.get(key)
    if f is None or f.value is None:
        return "—"
    v = f.value
    if isinstance(v, dict):
        return " ".join(str(x) for x in v.values())
    return str(v)


def build_pdf(data: ReviewData) -> bytes:
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"DBS Contract Review — {data.document.filename}",
    )
    story: list[Flowable] = []
    d = data.document

    # Cover
    story.append(Paragraph("DBS Contract Review Report", styles["title"]))
    story.append(Paragraph(d.filename, styles["body"]))
    story.append(Spacer(1, 6))
    story.append(
        _table(
            ["Field", "Value"],
            [
                ["Client / Counterparty", d.client or "—"],
                ["Contractor", d.contractor or "—"],
                ["Review date", datetime.now(UTC).strftime("%Y-%m-%d")],
                ["Reviewer", "DBS Contract Review System"],
                ["Classification", "Confidential — Internal DBS Circulation"],
            ],
            styles,
            col_widths=[45 * mm, 125 * mm],
        )
    )

    # 1. Executive summary
    story.append(Paragraph("1. Executive Summary", styles["h1"]))
    critical = data.severity_counts.get("critical", 0)
    high = data.severity_counts.get("high", 0)
    story.append(
        _table(
            ["Metric", "Value"],
            [
                ["Contract value", _fact(data, "contract_value")],
                ["Duration", _fact(data, "duration")],
                ["Critical risks", str(critical)],
                ["High risks", str(high)],
                ["Findings total", str(len(data.findings_sorted))],
                ["Management approval required", ", ".join(data.approval_rules) or "None"],
                [
                    "Missing information items",
                    str(sum(1 for r in data.register if r.rule == "MISSING-INFO")),
                ],
            ],
            styles,
            col_widths=[65 * mm, 105 * mm],
        )
    )
    key_issues = [r for r in data.register if r.severity in ("critical", "high")][:8]
    if key_issues:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Key negotiation issues:", styles["body"]))
        for r in key_issues:
            story.append(
                Paragraph(
                    f"• <b>{r.display_id}</b> — {r.finding} ({r.required_action})",
                    styles["bullet"],
                )
            )

    # 2. Snapshot
    story.append(Paragraph("2. Contract Snapshot", styles["h1"]))
    pt = data.facts.get("payment_terms_days")
    av = data.facts.get("availability_target")
    story.append(
        _table(
            ["Field", "Value"],
            [
                ["Client", d.client or "—"],
                ["Contractor", d.contractor or "—"],
                ["Contract value", _fact(data, "contract_value")],
                ["Currency", d.currency or "—"],
                ["Duration", _fact(data, "duration")],
                ["Effective date", d.start_date.strftime("%Y-%m-%d") if d.start_date else "—"],
                ["Expiry date", d.end_date.strftime("%Y-%m-%d") if d.end_date else "—"],
                ["Payment terms", f"{pt.value} days" if pt and pt.value is not None else "—"],
                ["Availability", f"{av.value}%" if av and av.value is not None else "—"],
                ["Liability cap", _fact(data, "liability_cap")],
                ["LD rate", _fact(data, "ld_rate")],
                ["Clauses analysed", str(data.clause_count)],
            ],
            styles,
            col_widths=[50 * mm, 120 * mm],
        )
    )

    # 3. Risk register
    story.append(Paragraph("3. Risk Register", styles["h1"]))
    if data.register:
        story.append(
            _table(
                [
                    "ID",
                    "Sev",
                    "Category",
                    "Clause",
                    "Finding",
                    "Exposure",
                    "DBS Position",
                    "Action",
                ],
                [
                    [
                        r.display_id,
                        r.severity,
                        r.category,
                        r.clause[:40],
                        r.finding[:70],
                        f"{r.exposure:,.0f}" if r.exposure is not None else "—",
                        r.dbs_position[:70],
                        r.required_action[:60],
                    ]
                    for r in data.register
                ],
                styles,
                col_widths=[14 * mm, 14 * mm, 20 * mm, 28 * mm, 34 * mm, 18 * mm, 24 * mm, 24 * mm],
            )
        )
    else:
        story.append(Paragraph("No findings recorded.", styles["body"]))

    # 4. Critical findings detail
    story.append(Paragraph("4. Critical Findings", styles["h1"]))
    detailed = [r for r in data.register if r.severity in ("critical", "high")]
    if not detailed:
        story.append(Paragraph("No critical or high findings.", styles["body"]))
    for r in detailed:
        story.append(Paragraph(f"{r.display_id} — {r.finding}", styles["h2"]))
        story.append(
            _table(
                ["Field", "Detail"],
                [
                    ["Severity", r.severity],
                    ["Source", r.clause],
                    ["Risk", r.dbs_position],
                    ["Action", r.required_action],
                    ["Rule", r.rule or "—"],
                    ["Evidence", (r.source_text or "—")[:300]],
                ],
                styles,
                col_widths=[24 * mm, 146 * mm],
            )
        )
        story.append(Spacer(1, 4))

    # 5. Financial exposure
    story.append(Paragraph("5. Financial Exposure", styles["h1"]))
    if data.exposures:
        story.append(
            _table(
                ["Scenario", "Result", "Ccy", "Formula", "Assumption"],
                [
                    [
                        e.scenario,
                        f"{float(e.result):,.2f}",
                        e.currency,
                        e.formula[:80],
                        e.assumption[:100],
                    ]
                    for e in data.exposures
                ],
                styles,
                col_widths=[34 * mm, 26 * mm, 12 * mm, 50 * mm, 48 * mm],
            )
        )
    for n in data.cannot_calculate:
        story.append(
            Paragraph(
                f"• Cannot calculate reliably — {n['metric']}: {n['reason']}.",
                styles["bullet"],
            )
        )

    # 6. Obligations
    story.append(Paragraph("6. Obligation Matrix", styles["h1"]))
    if data.obligations:
        story.append(
            _table(
                ["Party", "Obligation", "Trigger", "Frequency", "Source"],
                [
                    [
                        o.party,
                        o.obligation[:90],
                        (o.trigger or "—")[:40],
                        o.frequency or "—",
                        o.source_reference,
                    ]
                    for o in data.obligations
                ],
                styles,
                col_widths=[22 * mm, 62 * mm, 34 * mm, 18 * mm, 34 * mm],
            )
        )
    else:
        story.append(Paragraph("No obligations extracted.", styles["body"]))

    # 7. Missing information
    missing = [r for r in data.register if r.rule == "MISSING-INFO"]
    if missing:
        story.append(Paragraph("7. Missing Information / Clarifications", styles["h1"]))
        for r in missing:
            story.append(Paragraph(f"• {r.finding} — {r.required_action}", styles["bullet"]))

    doc.build(story)
    return buf.getvalue()
