export function formatMoney(
  value: number,
  currency: string | null | undefined,
  compact = false,
): string {
  const symbols: Record<string, string> = { USD: "$", EUR: "€", GBP: "£", SGD: "S$" };
  const symbol = currency ? (symbols[currency] ?? `${currency} `) : "";
  if (compact && Math.abs(value) >= 1_000_000) {
    return `${symbol}${(value / 1_000_000).toFixed(1)}M`;
  }
  return (
    symbol +
    value.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
  );
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatBytes(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
