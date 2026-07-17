export function formatCredits(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  if (value === 0) return '0'
  if (value >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (value >= 1) return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
  return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}
