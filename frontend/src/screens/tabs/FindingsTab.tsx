import { useMemo, useState } from "react";
import { SeverityBadge } from "../../components/SeverityBadge";
import { EmptyState, ErrorState, SkeletonList } from "../../components/States";
import { formatMoney } from "../../lib/format";
import type { Finding, Severity } from "../../lib/types";

const ORDER: Severity[] = ["critical", "high", "medium", "low", "informational"];

function FindingCard({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-xl border border-separator bg-surface">
      <div className="flex items-start gap-3 p-4">
        <SeverityBadge severity={f.severity} />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] leading-snug font-semibold">{f.finding}</p>
          <p className="mt-1 text-xs text-secondary-label">
            {f.category} · {f.source_reference}
            {f.financial_impact != null && (
              <span className="tnum">
                {" · "}
                {formatMoney(f.financial_impact, "USD")} exposure
              </span>
            )}
          </p>
          <p className="mt-2 text-sm text-label/90">{f.risk}</p>
          <p className="mt-1.5 text-sm">
            <span className="font-medium text-accent">Action: </span>
            {f.recommendation}
          </p>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="mt-2 text-xs font-medium text-accent hover:underline"
          >
            {open ? "Hide evidence" : "Show evidence"}
          </button>
          {open && (
            <blockquote className="mt-2 rounded-lg bg-surface-2 p-3 font-mono text-xs leading-relaxed text-secondary-label">
              “{f.source_text.slice(0, 500)}
              {f.source_text.length > 500 ? "…" : ""}”
              <footer className="mt-1.5 not-italic font-sans text-[11px]">
                {f.source_reference}
                {f.dbs_policy_rule && ` · Playbook rule ${f.dbs_policy_rule}`}
              </footer>
            </blockquote>
          )}
        </div>
      </div>
    </li>
  );
}

export function FindingsTab({
  findings,
  loading,
  error,
  onRetry,
}: {
  findings: Finding[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [filter, setFilter] = useState<Severity | "all">("all");

  const counts = useMemo(() => {
    const c: Partial<Record<Severity, number>> = {};
    for (const f of findings ?? []) c[f.severity] = (c[f.severity] ?? 0) + 1;
    return c;
  }, [findings]);

  const visible = useMemo(() => {
    const list = (findings ?? []).filter((f) => filter === "all" || f.severity === filter);
    return [...list].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  }, [findings, filter]);

  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading || findings === null) return <SkeletonList rows={3} />;
  if (findings.length === 0)
    return (
      <EmptyState
        title="No findings"
        body="No playbook violations were detected in this contract. Check the Exposure and Obligations tabs for the full review."
      />
    );

  const chips: Array<{ id: Severity | "all"; label: string }> = [
    { id: "all", label: `All ${findings.length}` },
    ...ORDER.filter((s) => counts[s]).map((s) => ({
      id: s,
      label: `${s.charAt(0).toUpperCase()}${s.slice(1)} ${counts[s]}`,
    })),
  ];

  return (
    <div>
      <div
        role="group"
        aria-label="Filter findings by severity"
        className="flex flex-wrap gap-2"
      >
        {chips.map((c) => (
          <button
            key={c.id}
            type="button"
            aria-pressed={filter === c.id}
            onClick={() => setFilter(c.id)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
              filter === c.id
                ? "bg-accent text-white"
                : "border border-separator bg-surface text-secondary-label hover:text-label"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>
      <ul className="mt-4 space-y-3">
        {visible.map((f) => (
          <FindingCard key={f.id} f={f} />
        ))}
      </ul>
    </div>
  );
}
