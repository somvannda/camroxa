import { describe, expect, it } from "vitest";

import { formatValue } from "@/components/studio/ParamKnob";

/** W5 B-51/B-52: Hz readouts kept a trailing .0 in the 1000–9999 range. */
describe("knob value formatting", () => {
  it("drops the trailing zero for kilohertz", () => {
    expect(formatValue(1000, "hz")).toBe("1khz");
    expect(formatValue(4000, "hz")).toBe("4khz");
    expect(formatValue(12000, "hz")).toBe("12khz");
    expect(formatValue(4500, "hz")).toBe("4.5khz");
  });

  it("keeps plain hertz below 1000", () => {
    expect(formatValue(120, "hz")).toBe("120hz");
    expect(formatValue(999, "hz")).toBe("999hz");
  });

  it("leaves the other units as they were", () => {
    expect(formatValue(-6, "db")).toBe("-6db");
    expect(formatValue(250, "ms")).toBe("250ms");
    expect(formatValue(50, "%")).toBe("50%");
    expect(formatValue(0.5, undefined, true)).toBe("50%");
  });
});
