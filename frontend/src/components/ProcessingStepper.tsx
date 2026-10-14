const STEPS = [
  { id: "text", label: "Reading document" },
  { id: "facts", label: "Extracting facts" },
  { id: "risk", label: "Playbook risk analysis" },
  { id: "economics", label: "Calculating exposure" },
  { id: "ready", label: "Preparing report" },
];

/**
 * Determinate-feel processing view: shows what the system is doing, per HIG
 * transparency + feedback principles (DESIGN.md §1, §6).
 */
export function ProcessingStepper({ status }: { status: string }) {
  const currentIndex =
    status === "uploaded" ? 0 : status === "processing" ? 2 : STEPS.length;

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-separator bg-surface p-6">
      <p className="text-sm font-semibold">Reviewing your contract…</p>
      <p className="mt-1 text-sm text-secondary-label">
        Extraction, risk analysis and economics run automatically. This page
        updates as each step finishes.
      </p>
      <ol className="mt-5 space-y-3" aria-live="polite">
        {STEPS.map((step, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <li key={step.id} className="flex items-center gap-3 text-sm">
              <span
                className={`grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold ${
                  done
                    ? "bg-success text-white"
                    : active
                      ? "bg-accent text-white"
                      : "bg-surface-2 text-tertiary-label"
                }`}
                aria-hidden
              >
                {done ? "✓" : i + 1}
              </span>
              <span
                className={
                  active ? "font-medium text-label" : done ? "text-secondary-label" : "text-tertiary-label"
                }
              >
                {step.label}
              </span>
              {active && (
                <span className="ml-auto size-2 animate-pulse rounded-full bg-accent" aria-hidden />
              )}
            </li>
          );
        })}
      </ol>
      <div
        className="mt-5 h-1.5 overflow-hidden rounded-full bg-surface-2"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={STEPS.length}
        aria-valuenow={currentIndex}
      >
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${(currentIndex / STEPS.length) * 100}%` }}
        />
      </div>
    </div>
  );
}
