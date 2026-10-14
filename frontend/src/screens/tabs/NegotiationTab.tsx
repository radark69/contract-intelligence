import { EmptyState, ErrorState, SkeletonList } from "../../components/States";
import { SeverityBadge } from "../../components/SeverityBadge";
import type { RiskRegister, Severity } from "../../lib/types";

const ORDER: Severity[] = ["critical", "high", "medium", "low", "informational"];

export function NegotiationTab({
  register,
  loading,
  error,
  onRetry,
}: {
  register: RiskRegister | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading || register === null) return <SkeletonList rows={3} />;

  const priorities = [...register.rows]
    .filter((r) => r.severity === "critical" || r.severity === "high")
    .sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  const missing = register.rows.filter((r) => r.dbs_policy_rule === "MISSING-INFO");
  const approval = register.management_approval_rule_ids;

  if (priorities.length === 0 && missing.length === 0 && approval.length === 0)
    return (
      <EmptyState
        title="Nothing to negotiate"
        body="No critical or high-severity issues, approval triggers or clarifications were found for this contract."
      />
    );

  return (
    <div className="space-y-6">
      {approval.length > 0 && (
        <section className="rounded-xl border border-high/30 bg-high-tint p-4">
          <h3 className="text-sm font-semibold text-high">
            Management approval required
          </h3>
          <p className="mt-1 text-sm text-secondary-label">
            This contract triggers DBS approval rules:{" "}
            <span className="font-mono text-xs">{approval.join(", ")}</span>. Escalate
            before signing.
          </p>
        </section>
      )}

      <section>
        <h3 className="text-base font-semibold">Priority negotiation actions</h3>
        <p className="mt-0.5 text-sm text-secondary-label">
          Ordered by severity — resolve these before softer points.
        </p>
        <ol className="mt-3 space-y-3">
          {priorities.map((r, i) => (
            <li
              key={r.id}
              className="flex gap-3 rounded-xl border border-separator bg-surface p-4"
            >
              <span className="tnum grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-bold text-secondary-label">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={r.severity} />
                  <span className="text-xs text-secondary-label">{r.clause}</span>
                </div>
                <p className="mt-1.5 text-[15px] font-medium">{r.finding}</p>
                <p className="mt-1 text-sm text-secondary-label">{r.dbs_position}</p>
                <p className="mt-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
                  <span className="font-semibold text-accent">Ask: </span>
                  {r.required_action}
                </p>
              </div>
            </li>
          ))}
        </ol>
        {priorities.length === 0 && (
          <p className="mt-2 text-sm text-secondary-label">
            No critical or high-severity items.
          </p>
        )}
      </section>

      {missing.length > 0 && (
        <section>
          <h3 className="text-base font-semibold">Clarifications to request</h3>
          <ul className="mt-3 space-y-2">
            {missing.map((r) => (
              <li
                key={r.id}
                className="flex items-start gap-2.5 rounded-lg border border-separator bg-surface px-4 py-3 text-sm"
              >
                <span aria-hidden className="mt-0.5 text-tertiary-label">?</span>
                <span>
                  {r.finding}{" "}
                  <span className="text-secondary-label">— {r.required_action}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
