import { describe, expect, it } from "vitest";
import { compareVersions, parseUpdateManifest } from "../../electron/services/updates";

describe("updates", () => {
  it("compares dotted versions", () => {
    expect(compareVersions("2.0.1", "2.0.0")).toBe(1);
    expect(compareVersions("2.0.0", "2.0.0")).toBe(0);
    expect(compareVersions("v1.9.9", "2.0.0")).toBe(-1);
  });

  it("accepts a newer manifest and rejects old or invalid ones", () => {
    expect(
      parseUpdateManifest(
        { version: "2.0.1", mandatory: true, notes: "Security fix", url: "https://example.com/a.exe" },
        "2.0.0",
      ),
    ).toEqual({
      version: "2.0.1",
      mandatory: true,
      notes: "Security fix",
      url: "https://example.com/a.exe",
      publishedAt: undefined,
    });
    expect(parseUpdateManifest({ version: "2.0.0" }, "2.0.0")).toBeNull();
    expect(parseUpdateManifest({ version: "2.0.1", url: "http://example.com/a.exe" }, "2.0.0")?.url).toBeUndefined();
    expect(parseUpdateManifest({}, "2.0.0")).toBeNull();
  });
});
