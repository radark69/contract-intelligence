import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { DocumentDetail } from "./types";

const POLL_STATUSES = new Set(["uploaded", "processing"]);

/** Poll document status while the backend is working (HIG: transparent feedback). */
export function useDocumentPoll(id: string): {
  doc: DocumentDetail | null;
  error: string | null;
  refresh: () => void;
} {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const d = await api.getDocument(id);
        if (cancelled) return;
        setDoc(d);
        setError(null);
        if (POLL_STATUSES.has(d.status)) {
          timer.current = window.setTimeout(() => setTick((t) => t + 1), 1500);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load document");
      }
    }
    void load();
    return () => {
      cancelled = true;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [id, tick]);

  return { doc, error, refresh: () => setTick((t) => t + 1) };
}
