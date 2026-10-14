import type { DocumentStatus } from "../lib/types";

const STYLES: Record<DocumentStatus, string> = {
  uploaded: "bg-surface-2 text-secondary-label",
  processing: "bg-accent/12 text-accent",
  extracted: "bg-accent/12 text-accent",
  analyzed: "bg-success-tint text-success",
  reported: "bg-success-tint text-success",
  failed: "bg-critical-tint text-critical",
};

const LABELS: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  extracted: "Extracted",
  analyzed: "Ready",
  reported: "Reported",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {(status === "processing" || status === "extracted") && (
        <span className="size-1.5 animate-pulse rounded-full bg-current" aria-hidden />
      )}
      {LABELS[status]}
    </span>
  );
}
