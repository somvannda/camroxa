/** Format display credits (supports fractional amounts). */
export function formatCredits(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (value === 0) return '0';
  if (value >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (value >= 1) return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
}

/** Format USD with extra precision for sub-cent micro-credit amounts. */
export function formatDollars(dollars: number | null | undefined): string {
  if (dollars == null || Number.isNaN(dollars)) return '—';
  if (dollars === 0) return '$0.0000';
  const abs = Math.abs(dollars);
  if (abs >= 0.01) {
    return `$${dollars.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')}`;
  }
  // GCV $0.01/credit → 0.0001 cr = $0.000001; need up to 8 decimal places.
  return `$${dollars.toFixed(8).replace(/0+$/, '').replace(/\.$/, '')}`;
}
