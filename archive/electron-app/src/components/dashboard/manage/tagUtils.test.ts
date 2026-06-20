import { describe, expect, it } from "vitest";
import { parseTags } from "@/components/dashboard/manage/tagUtils";

describe("parseTags", () => {
  it("splits, trims, and drops empties", () => {
    expect(parseTags("  a, b ,, c  ")).toEqual(["a", "b", "c"]);
  });
});

