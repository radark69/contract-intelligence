import { api } from "../../lib/api";

const FORMATS = [
  {
    fmt: "docx" as const,
    name: "Word report",
    ext: "DOCX",
    desc: "Full review report — executive summary, snapshot, risk register, findings, exposure and obligations. Editable for circulation.",
    primary: true,
  },
  {
    fmt: "pdf" as const,
    name: "PDF report",
    ext: "PDF",
    desc: "The same report rendered to PDF for fixed-layout sharing.",
    primary: false,
  },
  {
    fmt: "xlsx" as const,
    name: "Risk register",
    ext: "XLSX",
    desc: "Spreadsheet register with severity, exposure, playbook rules and evidence — ready for filtering.",
    primary: false,
  },
];

export function DownloadTab({ documentId }: { documentId: string }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary-label">
        Reports are generated on demand from the current review data.
      </p>
      <ul className="grid gap-3 sm:grid-cols-3">
        {FORMATS.map((f) => (
          <li
            key={f.fmt}
            className="flex flex-col rounded-xl border border-separator bg-surface p-4"
          >
            <div className="flex items-center gap-2">
              <span className="grid size-9 place-items-center rounded-lg bg-surface-2 text-[10px] font-bold tracking-wider text-secondary-label">
                {f.ext}
              </span>
              <p className="text-sm font-semibold">{f.name}</p>
            </div>
            <p className="mt-2 flex-1 text-xs leading-relaxed text-secondary-label">
              {f.desc}
            </p>
            <a
              href={api.reportUrl(documentId, f.fmt)}
              download
              className={`mt-4 inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors active:scale-[0.98] ${
                f.primary
                  ? "bg-accent text-white hover:bg-accent-hover"
                  : "border border-separator bg-surface text-label hover:bg-surface-2"
              }`}
            >
              Download {f.ext}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
