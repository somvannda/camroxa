export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not provided";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function classNames(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}
