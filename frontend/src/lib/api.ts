import type {
  DocSummary,
  DocumentDetail,
  ExposuresResponse,
  Fact,
  Finding,
  Obligation,
  RiskRegister,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export interface UploadProgress {
  loaded: number;
  total: number;
}

function uploadDocument(
  file: File,
  onProgress: (p: UploadProgress) => void,
): Promise<{ id: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    xhr.open("POST", `${BASE}/documents/upload`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress({ loaded: e.loaded, total: e.total });
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as { id: string });
      } else {
        let detail = xhr.statusText;
        try {
          const body = JSON.parse(xhr.responseText);
          detail = body.detail ?? detail;
        } catch {
          /* keep statusText */
        }
        reject(new ApiError(xhr.status, detail));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error — is the backend running?"));
    xhr.send(form);
  });
}

function startExtraction(id: string): Promise<void> {
  return fetch(`${BASE}/documents/${id}/extract`, { method: "POST" }).then((res) => {
    if (!res.ok && res.status !== 409) {
      throw new ApiError(res.status, `Extraction failed (${res.status})`);
    }
  });
}

export const api = {
  listDocuments: () => request<DocSummary[]>("/documents"),
  getDocument: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  uploadDocument,
  startExtraction,
  findings: (id: string) => request<Finding[]>(`/documents/${id}/findings`),
  riskRegister: (id: string) => request<RiskRegister>(`/documents/${id}/risk-register`),
  exposures: (id: string) => request<ExposuresResponse>(`/documents/${id}/exposures`),
  obligations: (id: string) => request<Obligation[]>(`/documents/${id}/obligations`),
  facts: (id: string) => request<Fact[]>(`/documents/${id}/facts`),
  reportUrl: (id: string, fmt: "docx" | "pdf" | "xlsx") =>
    `${BASE}/documents/${id}/report.${fmt}`,
};
