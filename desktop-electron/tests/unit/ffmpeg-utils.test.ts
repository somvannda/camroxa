import { describe, expect, it } from "vitest";
import { parseProgressLine, progressPercent } from "../../electron/services/ffmpeg-utils";

describe("ffmpeg utils", () => {
  it("parses progress key/value lines", () => {
    expect(parseProgressLine("frame=42")).toEqual({ key: "frame", value: "42" });
    expect(parseProgressLine("out_time_ms=1200000")).toEqual({
      key: "out_time_ms",
      value: "1200000",
    });
    expect(parseProgressLine("not a kv line")).toBeNull();
  });

  it("clamps progress", () => {
    expect(progressPercent(5000, 10)).toBe(50);
    expect(progressPercent(20000, 10)).toBe(100);
    expect(progressPercent(5000, 0)).toBe(0);
  });
});
