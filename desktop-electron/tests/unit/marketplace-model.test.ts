import { describe, expect, it } from "vitest";
import {
  catalogSchema,
  formatPrice,
  installLabel,
  kindLabel,
  kindParam,
  licenseLabel,
  normalizeSearch,
  schemaLabel,
  schemaPolicy,
  supportsPipeline,
  totalPages,
} from "../../src/features/marketplace/marketplace-model";
import type { MarketplaceItem } from "../../src/features/marketplace/marketplace-types";

function item(overrides: Partial<MarketplaceItem> = {}): MarketplaceItem {
  return {
    id: "item-1",
    name: "Night Drive",
    description: "A quiet long-form template",
    version: "1.2.0",
    author: "Camxora",
    kind: "video",
    tags: [],
    status: "enabled",
    price: 0,
    preview_url: "/marketplace/items/item-1/preview",
    created_at: "2026-11-01T00:00:00Z",
    ...overrides,
  };
}

describe("marketplace model", () => {
  it("formats free and paid prices", () => {
    expect(formatPrice(0)).toBe("Free");
    expect(formatPrice(-1)).toBe("Free");
    expect(formatPrice(12.5)).toBe("$12.50");
  });

  it("detects legacy templates from schema hints and known tags", () => {
    expect(catalogSchema(item())).toBe("vizzy");
    expect(catalogSchema(item({ schema: "legacy" }))).toBe("legacy");
    expect(catalogSchema(item({ template_schema: "camxora-v1" }))).toBe("legacy");
    expect(catalogSchema(item({ tags: ["legacy"] }))).toBe("legacy");
    expect(catalogSchema(item({ tags: ["Night", "moody"] }))).toBe("vizzy");
    expect(supportsPipeline("legacy")).toBe(false);
    expect(supportsPipeline("vizzy")).toBe(true);
  });

  it("labels schema policy and licence", () => {
    expect(schemaLabel("legacy")).toBe("Legacy Camxora");
    expect(schemaPolicy("legacy")).toContain("not supported in Camxora Desktop 2.0.0");
    expect(schemaPolicy("vizzy")).toBeNull();
    expect(licenseLabel(item())).toBe("Not listed");
    expect(licenseLabel(item({ licence: "Personal use" }))).toBe("Personal use");
  });

  it("formats kind labels and filters", () => {
    expect(kindLabel("reel")).toBe("Reel");
    expect(kindLabel("video")).toBe("Video");
    expect(kindLabel("long")).toBe("Long");
    expect(kindParam("all")).toBeUndefined();
    expect(kindParam("video")).toBe("video");
  });

  it("computes pagination boundaries", () => {
    expect(totalPages(0)).toBe(1);
    expect(totalPages(20)).toBe(1);
    expect(totalPages(21)).toBe(2);
    expect(totalPages(41)).toBe(3);
  });

  it("normalises search and install labels", () => {
    expect(normalizeSearch("  night   drive ")).toBe("night drive");
    expect(installLabel(false, false)).toBe("Install");
    expect(installLabel(true, false)).toBe("Reinstall");
    expect(installLabel(true, true)).toBe("Installing…");
  });
});
