import type { Severity } from "../lib/types";

const STYLES: Record<Severity, string> = {
  critical: "bg-critical-tint text-critical",
  high: "bg-high-tint text-high",
  medium: "bg-medium-tint text-medium",
  low: "bg-low-tint text-low",
  informational: "bg-low-tint text-low",
};

const LABELS: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  informational: "Info",
};

/** Severity = color + text, never color alone (HIG: Color; DESIGN.md §4). */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide ${STYLES[severity] ?? STYLES.low}`}
    >
      {LABELS[severity] ?? severity}
    </span>
  );
}
