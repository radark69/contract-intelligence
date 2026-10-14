import { useMemo, useState } from "react";
import { EmptyState, ErrorState, SkeletonList } from "../../components/States";
import type { Obligation } from "../../lib/types";

export function ObligationsTab({
  obligations,
  loading,
  error,
  onRetry,
}: {
  obligations: Obligation[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [party, setParty] = useState<"all" | "client" | "contractor">("all");

  const parties = useMemo(() => {
    const set = new Set<string>();
    for (const o of obligations ?? []) set.add(o.party.toLowerCase());
    return set;
  }, [obligations]);

  const visible = (obligations ?? []).filter(
    (o) => party === "all" || o.party.toLowerCase().includes(party),
  );

  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading || obligations === null) return <SkeletonList rows={3} />;
  if (obligations.length === 0)
    return (
      <EmptyState
        title="No obligations extracted"
        body="Obligations with explicit triggers and frequencies appear here once extraction completes."
      />
    );

  const filters: Array<{ id: "all" | "client" | "contractor"; label: string }> = [
    { id: "all", label: `All ${obligations.length}` },
  ];
  if (parties.has("client")) filters.push({ id: "client", label: "Client" });
  if (parties.has("contractor")) filters.push({ id: "contractor", label: "Contractor" });

  return (
    <div>
      <div role="group" aria-label="Filter obligations by party" className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            aria-pressed={party === f.id}
            onClick={() => setParty(f.id)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
              party === f.id
                ? "bg-accent text-white"
                : "border border-separator bg-surface text-secondary-label hover:text-label"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Grouped table on desktop, stacked cards on mobile (HIG: adaptive layout) */}
      <div className="mt-4 hidden overflow-hidden rounded-xl border border-separator bg-surface sm:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-separator text-xs tracking-wide text-secondary-label uppercase">
            <tr>
              <th className="px-4 py-2.5 font-medium">Party</th>
              <th className="px-4 py-2.5 font-medium">Obligation</th>
              <th className="px-4 py-2.5 font-medium">Trigger</th>
              <th className="px-4 py-2.5 font-medium">Frequency</th>
              <th className="px-4 py-2.5 font-medium">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-separator">
            {visible.map((o) => (
              <tr key={o.id}>
                <td className="px-4 py-3 font-medium whitespace-nowrap">{o.party}</td>
                <td className="px-4 py-3">{o.obligation}</td>
                <td className="px-4 py-3 text-secondary-label">{o.trigger ?? "—"}</td>
                <td className="px-4 py-3 text-secondary-label">{o.frequency ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs text-secondary-label">
                  {o.source_reference}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="mt-4 space-y-3 sm:hidden">
        {visible.map((o) => (
          <li key={o.id} className="rounded-xl border border-separator bg-surface p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-accent">{o.party}</span>
              <span className="font-mono text-[11px] text-secondary-label">
                {o.source_reference}
              </span>
            </div>
            <p className="mt-1.5 text-sm">{o.obligation}</p>
            <p className="mt-1 text-xs text-secondary-label">
              {o.trigger ?? "No trigger"} · {o.frequency ?? "frequency n/a"}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
