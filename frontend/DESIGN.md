# Design Brief — Apple HIG Applied to DBS Contract Reviewer

Distilled from Apple Human Interface Guidelines
(developer.apple.com/design/human-interface-guidelines) and applied to this app.
Sprint 9 UI must follow these rules.

## 1. Principles (HIG: Design principles)

| HIG principle | What it means here |
|---|---|
| **Be clear and direct** | Every screen answers one question. Upload says "drop a contract". Findings say "what's wrong". No ambiguous icons without labels. |
| **Keep focused** | The app has one job: review a contract and download a report. Upload is the first and largest action on the landing view; nothing competes with it. |
| **Stay out of the way** | Content (findings, evidence) is the hero. Chrome — nav, toolbars — is minimal and recedes. No decorative elements between the user and the evidence. |
| **Be transparent** | Processing shows what the system is doing (extracting → facts → risk → economics → report). No hidden state, no fabricated confidence. |
| **Familiarity + consistency** | Use known patterns: card lists, tables, badges, tabs. Once a severity badge looks a certain way, it looks that way everywhere. |
| **Clear feedback** | Upload progress, extraction status, button pressed states, error toasts — every action gets an immediate response. |
| **Design for everyone** | Accessibility first: contrast, keyboard nav, semantic HTML, screen-reader labels, touch targets ≥44×44pt equivalents. |
| **Include just what's necessary** | Progressive disclosure: dashboard shows counts; findings detail shows evidence. Don't dump 100 clauses on one screen. |
| **Establish hierarchy** | Severity and money drive hierarchy: critical findings first, largest exposures first, primary action (Download report) visually dominant. |
| **Quality sets the tone; delight ≠ decoration** | Precise wording (evidence quotes, exact formulas), smooth 200–300ms transitions, zero gratuitous animation. |

## 2. Layout (HIG: Layout)

- **Order by relative importance**: most important near top/leading side. Dashboard: status → counts → critical findings → everything else.
- **Align and group**: consistent left alignment; group related items with cards/separators, not just whitespace.
- **Progressive disclosure**: lists → detail views; tabs/sections for Findings / Exposure / Obligations / Negotiation.
- **Adapt gracefully**: max-width content column centered on large screens; single column on narrow. Stack actions vertically when space is tight.
- **No more than 2–3 controls side by side**; primary action (Download) is full-width in its bar or clearly filled.
- **Respect safe areas/margins**: page gutter ≥16px mobile, ≥24px desktop; consistent 8pt spacing grid.

## 3. Typography (HIG: Typography)

- **System font stack**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", …` — feels at home on Apple devices.
- **Text-style hierarchy** (weight + size, not color alone):
  - Large Title 28/34 bold — screen name only (one per screen)
  - Title 22/28 semibold — section headers
  - Headline 17/22 semibold — card titles, finding titles
  - Body 17/25 regular — findings, evidence
  - Subhead/footnote 13–15 — metadata, source refs (`Page 12, Clause 7.2`)
- **Legibility**: ≥4.5:1 text contrast (WCAG AA, per Apple accessibility criteria); no thin weights at small sizes; avoid truncating evidence text — wrap or link to detail.
- **Numeric/tabular alignment**: use `font-variant-numeric: tabular-nums` for money columns so figures align.

## 4. Color (HIG: Color)

- **Semantic roles, not raw values**: background, surface (card), label (primary text), secondaryLabel, separator, accent. Define once as CSS variables; support **light and dark**.
- **Accent reserved for emphasis**: primary actions and links only. One filled/accent button per view — the primary action (Upload / Download report).
- **Never color alone**: severity = color + text label (+ icon). Severity palette:
  - critical `#B00020`, high `#D96C00`, medium `#8A6D00`, low/neutral grays
- **Contrast**: 4.5:1 for text, 3:1 for non-text UI states (badges, borders, controls).
- **Don't redefine semantics**: destructive = red, success/OK = green, info = accent/blue — match platform conventions.

## 5. Components (HIG: Buttons, Tab bars, Materials)

- **Buttons**: roles — **primary** (filled, accent bg, one per view), **secondary** (tinted/plain), **destructive** (red, confirmed). ≥44pt hit area, system-like corner radius (~10–12px), clear pressed/hover/disabled states.
- **Tab bar / segmented nav** for the 4 review sections (Findings, Exposure, Obligations, Download) — prefer tabs over deep menus; ≤5 items, no overflow.
- **Materials → web equivalents**: sticky translucent header (`backdrop-filter: blur`) over scrolling content; content scrolls beneath, controls float above (HIG "controls vs content layer"). Never blur content behind text-heavy surfaces.
- **Tables/lists**: hairline separators, grouped rows, sticky headers; row height stable while loading (no layout jump).

## 6. States & feedback (HIG: feedback + progressive disclosure)

- **Every async flow shows state**: upload (progress bar) → processing (per-step status: Extracting text → Facts → Risk analysis → Economics) → done (auto-advance to dashboard).
- **Empty states** teach: "No contracts yet — upload a PDF or XLSX to start a review."
- **Error states** are specific and recoverable: "Couldn't read this file — save legacy .xls as .xlsx and retry."
- **Loading**: skeletons for cards/tables (never bare spinners for content), determinate progress for uploads.
- **Motion**: 150–300ms ease-out for state changes; respect `prefers-reduced-motion`.

## 7. Accessibility floor (non-negotiable)

- Semantic HTML + ARIA labels; full keyboard operability; visible focus rings (accent, 2px).
- Skip-to-content link; live regions for processing status (`aria-live="polite"`).
- Text resizes to 200% without breaking layout (no fixed-height text containers).
- Every icon-only control has an accessible name.
