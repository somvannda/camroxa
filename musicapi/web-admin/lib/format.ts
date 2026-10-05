/** Shared number/date formatters so every admin view renders values the same. */

export function usd(n: number): string {
  return `$${n.toFixed(2)}`;
}

export function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function num(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(n) ? n.toLocaleString() : "—";
}

export function dateTime(value: string | number | Date | null | undefined): string {
  if (!value) return "—";
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export function dateOnly(value: string | number | Date | null | undefined): string {
  if (!value) return "—";
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
}

/** Percentage with one decimal, or an em dash when there is no denominator. */
export function percent(success: number, total: number): string {
  if (total === 0) return "—";
  return `${((success / total) * 100).toFixed(1)}%`;
}
