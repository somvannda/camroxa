import type { MarketplaceItem, MarketplaceKind, MarketplaceSchema } from "./marketplace-types";

export const CATALOG_PAGE_SIZE = 20;
export const SEARCH_DEBOUNCE_MS = 300;

const LEGACY_TAGS = new Set([
  "legacy",
  "camxora-legacy",
  "old-camxora",
  "camxora-v1",
  "v1-template",
  "video-template-v1",
]);

function normalizeSchemaValue(value: unknown): MarketplaceSchema | null {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return null;
  if (["legacy", "camxora", "camxora-v1", "old-camxora", "v1"].includes(text)) return "legacy";
  if (["vizzy", "pipeline", "vizzy-pipeline", "2", "2.0", "2.0.0"].includes(text)) return "vizzy";
  return null;
}

/**
 * 2.0.0 only runs Vizzy pipeline templates. The catalog shape has no schema
 * field, so an explicit hint wins; otherwise known legacy tags mark the item.
 * Anything unmarked is treated as a 2.0.0 pipeline template.
 */
export function catalogSchema(item: MarketplaceItem): MarketplaceSchema {
  const explicit =
    normalizeSchemaValue(item.schema) ??
    normalizeSchemaValue(item.template_schema) ??
    normalizeSchemaValue((item as unknown as Record<string, unknown>).templateSchema);
  if (explicit) return explicit;
  const tags = Array.isArray(item.tags) ? item.tags : [];
  if (tags.some((tag) => LEGACY_TAGS.has(String(tag ?? "").trim().toLowerCase()))) return "legacy";
  return "vizzy";
}

export function supportsPipeline(schema: MarketplaceSchema): boolean {
  return schema === "vizzy";
}

export function schemaLabel(schema: MarketplaceSchema): string {
  return schema === "legacy" ? "Legacy Camxora" : "Vizzy";
}

export function schemaPolicy(schema: MarketplaceSchema): string | null {
  return schema === "legacy"
    ? "Old Camxora templates are not supported in Camxora Desktop 2.0.0 and cannot be selected by the pipeline."
    : null;
}

export function kindLabel(kind: string): string {
  const normalized = String(kind ?? "").trim().toLowerCase();
  if (!normalized) return "Template";
  if (normalized === "reel") return "Reel";
  if (normalized === "video") return "Video";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export function formatPrice(price: number | null | undefined): string {
  const value = Number(price ?? 0);
  if (!Number.isFinite(value) || value <= 0) return "Free";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(value);
}

export function totalPages(total: number, pageSize = CATALOG_PAGE_SIZE): number {
  const size = pageSize > 0 ? pageSize : CATALOG_PAGE_SIZE;
  return Math.max(1, Math.ceil(Math.max(0, Number(total) || 0) / size));
}

export function licenseLabel(item: MarketplaceItem): string {
  const value = item.licence ?? item.license;
  const text = typeof value === "string" ? value.trim() : "";
  return text || "Not listed";
}

export function normalizeSearch(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function kindParam(kind: MarketplaceKind): string | undefined {
  return kind === "all" ? undefined : kind;
}

export function installLabel(installed: boolean, installing: boolean): string {
  if (installing) return "Installing…";
  return installed ? "Reinstall" : "Install";
}
