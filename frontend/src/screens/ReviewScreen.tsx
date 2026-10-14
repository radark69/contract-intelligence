import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { useDocumentPoll } from "../lib/useDocumentPoll";
import { formatMoney } from "../lib/format";
import type {
  ExposuresResponse,
  Finding,
  Obligation,
  RiskRegister,
} from "../lib/types";
import { ErrorState, Skeleton } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";
import { ProcessingStepper } from "../components/ProcessingStepper";
import { TabBar, type TabDef } from "../components/TabBar";
import { FindingsTab } from "./tabs/FindingsTab";
import { ExposureTab } from "./tabs/ExposureTab";
import { ObligationsTab } from "./tabs/ObligationsTab";
import { NegotiationTab } from "./tabs/NegotiationTab";
import { DownloadTab } from "./tabs/DownloadTab";

const TABS: TabDef[] = [
  { id: "findings", label: "Findings" },
  { id: "exposure", label: "Exposure" },
  { id: "obligations", label: "Obligations" },
  { id: "negotiation", label: "Negotiation" },
  { id: "download", label: "Download" },
];

const ANALYSIS_STATUSES = new Set(["extracted", "analyzed", "reported"]);

function useResource<T>(
  active: boolean,
  fetcher: () => Promise<T>,
  deps: unknown[],
): { data: T | null; loading: boolean; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const key = JSON.stringify(deps) + nonce;
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, key]);

  return { data, loading, error, reload: () => setNonce((n) => n + 1) };
}

export function ReviewScreen() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const tab = searchParams.get("tab") ?? "findings";
  const { doc, error: docError, refresh } = useDocumentPoll(id);

  // Kick off extraction for freshly uploaded docs (status stays "uploaded").
  useEffect(() => {
    if (doc?.status === "uploaded") void api.startExtraction(doc.id).then(refresh);
  }, [doc?.status, doc?.id, refresh]);

  const analysisReady = doc != null && ANALYSIS_STATUSES.has(doc.status);
  const failed = doc?.status === "failed";

  const register = useResource<RiskRegister>(
    analysisReady,
    () => api.riskRegister(id),
    [analysisReady],
  );
  const findings = useResource<Finding[]>(
    analysisReady && tab === "findings",
    () => api.findings(id),
    [analysisReady, tab],
  );
  const exposures = useResource<ExposuresResponse>(
    analysisReady && tab === "exposure",
    () => api.exposures(id),
    [analysisReady, tab],
  );
  const obligations = useResource<Obligation[]>(
    analysisReady && tab === "obligations",
    () => api.obligations(id),
    [analysisReady, tab],
  );

  const retry = useCallback(() => {
    register.reload();
    findings.reload();
    exposures.reload();
    obligations.reload();
    refresh();
  }, [register, findings, exposures, obligations, refresh]);

  if (docError) return <ErrorState message={docError} onRetry={refresh} />;
  if (doc === null)
    return (
      <div className="space-y-4" role="status" aria-label="Loading document">
        <Skeleton className="h-24" />
        <Skeleton className="h-10" />
        <Skeleton className="h-64" />
      </div>
    );

  if (failed)
    return (
      <ErrorState
        message={doc.error_message ?? "Processing failed for this document."}
        onRetry={refresh}
      />
    );

  if (doc.status === "uploaded" || doc.status === "processing")
    return (
      <div className="fade-in">
        <p className="mb-6 text-sm text-secondary-label">{doc.filename}</p>
        <ProcessingStepper status={doc.status} />
      </div>
    );

  const counts = register.data?.severity_counts ?? {};
  const critical = counts.critical ?? 0;
  const high = counts.high ?? 0;

  return (
    <div className="fade-in">
      {/* Snapshot header — most important info at top (HIG: Layout) */}
      <div className="rounded-2xl border border-separator bg-surface p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold sm:text-2xl">{doc.filename}</h1>
            <p className="mt-1 text-sm text-secondary-label">
              {doc.client ?? "Client pending"}
              {doc.contractor && ` · ${doc.contractor}`}
              {doc.contract_type && ` · ${doc.contract_type}`}
            </p>
          </div>
          <StatusBadge status={doc.status} />
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-secondary-label">Contract value</dt>
            <dd className="tnum font-semibold">
              {doc.contract_value != null
                ? formatMoney(doc.contract_value, doc.currency)
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-secondary-label">Findings</dt>
            <dd className="tnum font-semibold">{register.data?.total ?? "…"}</dd>
          </div>
          <div>
            <dt className="text-xs text-secondary-label">Critical</dt>
            <dd className="tnum font-semibold text-critical">
              {register.data ? critical : "…"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-secondary-label">High</dt>
            <dd className="tnum font-semibold text-high">
              {register.data ? high : "…"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-5">
        <TabBar tabs={TABS} active={tab} />
      </div>

      <div className="mt-5" role="tabpanel" aria-label={tab}>
        {!analysisReady ? (
          <ErrorState message="Analysis is still running — this page refreshes automatically." />
        ) : tab === "findings" ? (
          <FindingsTab
            findings={findings.data}
            loading={findings.loading}
            error={findings.error}
            onRetry={findings.reload}
          />
        ) : tab === "exposure" ? (
          <ExposureTab
            data={exposures.data}
            loading={exposures.loading}
            error={exposures.error}
            onRetry={exposures.reload}
          />
        ) : tab === "obligations" ? (
          <ObligationsTab
            obligations={obligations.data}
            loading={obligations.loading}
            error={obligations.error}
            onRetry={obligations.reload}
          />
        ) : tab === "negotiation" ? (
          <NegotiationTab
            register={register.data}
            loading={register.loading}
            error={register.error}
            onRetry={retry}
          />
        ) : (
          <DownloadTab documentId={id} />
        )}
      </div>
    </div>
  );
}
