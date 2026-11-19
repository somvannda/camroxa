import { describe, expect, it } from "vitest";
import { redact, redactString } from "../../electron/services/redact";

describe("redact", () => {
  it("redacts secret keys recursively", () => {
    expect(
      redact({
        email: "person@example.com",
        nested: { refresh_token: "abc", safe: "ok" },
      }),
    ).toEqual({
      email: "[redacted]",
      nested: { refresh_token: "[redacted]", safe: "ok" },
    });
  });

  it("redacts bearer tokens and emails inside strings", () => {
    expect(redactString("Authorization: Bearer abc.def-123 and user@example.com")).toBe(
      "Authorization: Bearer [redacted] and [redacted-email]",
    );
  });
});
