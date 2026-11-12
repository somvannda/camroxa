import { describe, expect, it } from "vitest";

import { classifyStudioError } from "@/lib/studio-errors";

describe("Studio error taxonomy", () => {
  it("maps credit failures to the refusal copy", () => {
    expect(classifyStudioError("402 Insufficient credits.")).toEqual({
      kind: "credits",
      text: "Not enough credits. Buy more credits or view plans.",
    });
    expect(classifyStudioError(new Error("credit balance too low")).kind).toBe("credits");
  });

  it("uses the captured copyright copy for lyrics", () => {
    expect(
      classifyStudioError("Your lyrics contain copyrighted material. Please change it and try again.")
    ).toEqual({
      kind: "policy",
      text: "Couldn't generate that. Your lyrics contain copyrighted material. Please change it and try again.",
    });
  });

  it("keeps a generic policy refusal generic", () => {
    expect(classifyStudioError("Prompt blocked by policy.")).toEqual({
      kind: "policy",
      text: "That prompt was refused. Change it and try again.",
    });
  });

  it("maps edit conflicts and provider timeouts", () => {
    expect(classifyStudioError("Extend cannot be combined with other operations")).toEqual({
      kind: "conflict",
      text: "That edit conflicts with another operation. Wait for it to finish, then try again.",
    });
    expect(classifyStudioError("Timed out waiting for clip completion.")).toEqual({
      kind: "timeout",
      text: "The provider took too long. Try again with a shorter range.",
    });
  });

  it("preserves an unknown provider message and falls back when empty", () => {
    expect(classifyStudioError("No audio came back.")).toEqual({
      kind: "failed",
      text: "No audio came back.",
    });
    expect(classifyStudioError("", "Could not run that.")).toEqual({
      kind: "failed",
      text: "Could not run that.",
    });
  });
});
