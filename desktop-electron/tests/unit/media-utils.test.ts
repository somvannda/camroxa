import { describe, expect, it } from "vitest";
import { isPathInside, parseRange } from "../../electron/services/media-utils";

describe("media utils", () => {
  it("detects paths inside a root", () => {
    expect(isPathInside("C:/data", "C:/data/images/a.png")).toBe(true);
    expect(isPathInside("C:/data", "C:/data2/a.png")).toBe(false);
    expect(isPathInside("C:/data", "C:/data/../secret.txt")).toBe(false);
  });

  it("parses byte ranges", () => {
    expect(parseRange(null, 100)).toBeNull();
    expect(parseRange("bytes=0-9", 100)).toEqual({ start: 0, end: 9 });
    expect(parseRange("bytes=90-", 100)).toEqual({ start: 90, end: 99 });
    expect(parseRange("bytes=-10", 100)).toEqual({ start: 90, end: 99 });
    expect(parseRange("bytes=100-", 100)).toBe("invalid");
    expect(parseRange("bytes=9-2", 100)).toBe("invalid");
  });
});
