import path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveUnderBase } from "../../electron/shared/user-paths";

const base = path.resolve("C:/SUNO");

describe("resolveUnderBase", () => {
  it("keeps an absolute backend path", () => {
    const absolute = path.resolve("E:/Media/run");
    expect(resolveUnderBase(absolute, base)).toBe(path.normalize(absolute));
  });

  it("joins a portable run key under the Suno root", () => {
    expect(resolveUnderBase("bass-drive\\2026-11-22_Letters", base)).toBe(
      path.resolve(base, "bass-drive/2026-11-22_Letters"),
    );
  });

  it("returns an empty path unchanged", () => {
    expect(resolveUnderBase("", base)).toBe("");
    expect(resolveUnderBase("   ", base)).toBe("");
  });
});
