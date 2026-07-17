/** Display credits (1 credit = $0.01 at default GCV). API values are already display credits. */
export function formatCredits(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value === 0) return "0";
  if (value >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (value >= 1) return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

/** @deprecated Use formatCredits — kept for existing imports. */
export function formatCreditValue(value: number | null | undefined): string {
  return formatCredits(value);
}
