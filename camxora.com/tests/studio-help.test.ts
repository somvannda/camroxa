import { describe, expect, it } from "vitest";

import { HELP_ENTRIES, helpFor, SHORTCUTS } from "@/lib/studio-help";

describe("help registry", () => {
  it("gives every annotated control a name and a real sentence", () => {
    const ids = Object.keys(HELP_ENTRIES);
    expect(ids.length).toBeGreaterThan(10);
    for (const id of ids) {
      const entry = HELP_ENTRIES[id];
      expect(entry.title.trim().length, id).toBeGreaterThan(0);
      // A one-word title is fine; the body has to explain something.
      expect(entry.body.trim().length, id).toBeGreaterThan(25);
    }
  });

  it("has no entry without a corresponding id format", () => {
    for (const id of Object.keys(HELP_ENTRIES)) {
      expect(id).toMatch(/^[a-z][a-z-]*$/);
    }
  });

  it("returns null for unknown or missing ids instead of a blank card", () => {
    expect(helpFor("tempo")?.title).toBe("Tempo");
    expect(helpFor("nope")).toBeNull();
    expect(helpFor(null)).toBeNull();
    expect(helpFor(undefined)).toBeNull();
  });

  it("documents the bindings the editor actually implements", () => {
    const keys = SHORTCUTS.map((row) => row.keys).join(" | ");
    expect(keys).toContain("Ctrl/⌘ + Z");
    expect(keys).toContain("Shift + Z");
    expect(keys).toContain("Delete");
    expect(keys).toContain("Ctrl + Shift + ,");
    for (const row of SHORTCUTS) {
      expect(row.action.trim().length).toBeGreaterThan(3);
    }
  });

  it("mentions recording is not implemented where it would be misleading", () => {
    expect(HELP_ENTRIES["track-arm"].body.toLowerCase()).toContain("not implemented");
  });
});
