import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api, type UploadProgress } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";
import type { DocSummary } from "../lib/types";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";

const ACCEPT = ".pdf,.xlsx";

export function HomeScreen() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<DocSummary[] | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listDocuments()
      .then(setDocs)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load documents"));
  }, []);

  useEffect(load, [load]);

  // Reset file input on mount (handles browser back button)
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, []);

  async function handleFile(file: File) {
    setError(null);
    if (!/\.(pdf|xlsx)$/i.test(file.name)) {
      setError("Unsupported file — upload a PDF or .xlsx (save legacy .xls as .xlsx first).");
      return;
    }
    try {
      setProgress({ loaded: 0, total: file.size });
      const { id } = await api.uploadDocument(file, setProgress);
      await api.startExtraction(id);
      setProgress(null);
      navigate(`/documents/${id}`);
    } catch (e) {
      setProgress(null);
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Upload failed");
    }
  }

  return (
    <div className="fade-in">
      <h1 className="text-3xl font-bold tracking-tight sm:text-[28px]">Contract Review</h1>
      <p className="mt-1.5 text-base text-secondary-label">
        Upload a contract to extract facts, check it against the DBS playbook and
        download a professional review report.
      </p>

      {/* Upload — the primary, unambiguous action (HIG: keep focused) */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files[0];
          if (f) void handleFile(f);
        }}
        className={`mt-6 rounded-2xl border-2 border-dashed p-8 text-center transition-colors sm:p-10 ${
          dragOver ? "border-accent bg-accent/5" : "border-separator bg-surface"
        }`}
      >
        {progress ? (
          <div className="mx-auto max-w-sm" role="status" aria-live="polite">
            <p className="text-sm font-medium">Uploading…</p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{
                  width: `${progress.total ? (progress.loaded / progress.total) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        ) : (
          <>
            <p className="text-base font-semibold">Drag a contract here</p>
            <p className="mt-1 text-sm text-secondary-label">
              PDF or Excel (.xlsx), up to 100 MB
            </p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-4 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-hover active:scale-[0.98]"
            >
              Choose file…
            </button>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void handleFile(f);
                e.target.value = "";
              }}
            />
          </>
        )}
      </div>

      {error && (
        <div className="mt-4">
          <ErrorState message={error} />
        </div>
      )}

      <h2 className="mt-10 text-lg font-semibold">Recent reviews</h2>
      <div className="mt-3">
        {docs === null ? (
          <div className="space-y-3" role="status" aria-label="Loading documents">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : docs.length === 0 ? (
          <EmptyState
            title="No contracts yet"
            body="Upload a PDF or XLSX to start your first review. Files are processed privately on this server."
          />
        ) : (
          <ul className="divide-y divide-separator overflow-hidden rounded-2xl border border-separator bg-surface">
            {docs.map((d) => (
              <li key={d.id}>
                <Link
                  to={`/documents/${d.id}`}
                  className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-surface-2/60"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{d.filename}</p>
                    <p className="mt-0.5 truncate text-xs text-secondary-label">
                      {d.client ?? "Client pending"} · {formatDateTime(d.created_at)}
                    </p>
                  </div>
                  {d.contract_value != null && (
                    <span className="tnum hidden text-sm text-secondary-label sm:block">
                      {formatMoney(d.contract_value, "USD", true)}
                    </span>
                  )}
                  <StatusBadge status={d.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
