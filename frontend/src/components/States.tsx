import type { ReactNode } from "react";

/** Skeleton placeholder — never a bare spinner for content (DESIGN.md §6). */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-surface-2 ${className}`}
      aria-hidden
    />
  );
}

export function SkeletonList({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading content">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rounded-xl border border-separator bg-surface p-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-3 h-5 w-3/4" />
          <Skeleton className="mt-2 h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/** Empty states teach (DESIGN.md §6). */
export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-separator bg-surface px-6 py-12 text-center">
      <p className="text-base font-semibold">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-secondary-label">{body}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-critical/30 bg-critical-tint px-4 py-3 text-sm"
    >
      <p className="font-semibold text-critical">Something went wrong</p>
      <p className="mt-0.5 text-secondary-label">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-lg bg-surface px-3 py-1.5 text-xs font-medium text-label hover:bg-surface-2"
        >
          Try again
        </button>
      )}
    </div>
  );
}
