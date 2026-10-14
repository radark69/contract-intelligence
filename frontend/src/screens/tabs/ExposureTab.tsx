import { EmptyState, ErrorState, SkeletonList } from "../../components/States";
import { formatMoney } from "../../lib/format";
import type { ExposuresResponse } from "../../lib/types";

export function ExposureTab({
  data,
  loading,
  error,
  onRetry,
}: {
  data: ExposuresResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading || data === null) return <SkeletonList rows={3} />;

  const { exposures, cannot_calculate } = data;
  if (exposures.length === 0 && cannot_calculate.length === 0)
    return (
      <EmptyState
        title="No exposure calculated"
        body="Monetary facts were not found in this contract, so there is nothing to calculate. Facts appear after extraction completes."
      />
    );

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary-label">
        Every figure below shows its exact formula and assumptions — the system
        never fabricates missing inputs.
      </p>

      <ul className="grid gap-3 sm:grid-cols-2">
        {exposures.map((e) => (
          <li
            key={e.id}
            className="flex flex-col rounded-xl border border-separator bg-surface p-4"
          >
            <p className="text-xs font-medium tracking-wide text-secondary-label uppercase">
              {e.scenario}
            </p>
            <p className="tnum mt-1.5 text-2xl font-bold">
              {formatMoney(e.result, e.currency)}
            </p>
            <p className="mt-2 font-mono text-xs leading-relaxed text-accent">
              {e.formula}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-secondary-label">
              {e.assumption}
            </p>
          </li>
        ))}
      </ul>

      {cannot_calculate.length > 0 && (
        <section className="rounded-xl border border-separator bg-surface p-4">
          <h3 className="text-sm font-semibold">Cannot calculate reliably</h3>
          <ul className="mt-2 space-y-1.5 text-sm text-secondary-label">
            {cannot_calculate.map((n) => (
              <li key={n.metric}>
                <span className="font-medium text-label">{n.metric}</span> — {n.reason}.
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
