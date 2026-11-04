import { describe, expect, it } from "vitest";

import { clearDraft, describeDraft, draftKey, loadDraft, saveDraft } from "@/lib/studio-draft";

function fakeStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => Array.from(map.keys())[index] ?? null,
    removeItem: (key: string) => void map.delete(key),
    setItem: (key: string, value: string) => void map.set(key, value),
  } as Storage;
}

describe("studio draft", () => {
  it("round-trips a document", () => {
    const store = fakeStorage();
    saveDraft("p1", { lanes: [{ id: "a" }] }, store);
    const draft = loadDraft("p1", store);
    expect(draft).not.toBeNull();
    expect(draft?.data).toEqual({ lanes: [{ id: "a" }] });
    expect(typeof draft?.savedAt).toBe("string");
  });

  it("keys per project so two projects never collide", () => {
    const store = fakeStorage();
    saveDraft("p1", { n: 1 }, store);
    saveDraft("p2", { n: 2 }, store);
    expect(loadDraft("p1", store)?.data).toEqual({ n: 1 });
    expect(loadDraft("p2", store)?.data).toEqual({ n: 2 });
    expect(draftKey("p1")).not.toBe(draftKey("p2"));
  });

  it("clears a draft", () => {
    const store = fakeStorage();
    saveDraft("p1", { n: 1 }, store);
    clearDraft("p1", store);
    expect(loadDraft("p1", store)).toBeNull();
  });

  it("returns null for corrupt payloads instead of throwing", () => {
    const store = fakeStorage();
    store.setItem(draftKey("p1"), "{not json");
    expect(loadDraft("p1", store)).toBeNull();
    store.setItem(draftKey("p1"), JSON.stringify({ never: "data" }));
    expect(loadDraft("p1", store)).toBeNull();
  });

  it("survives a storage that throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("quota");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    } as unknown as Storage;
    expect(() => saveDraft("p1", {}, broken)).not.toThrow();
    expect(loadDraft("p1", broken)).toBeNull();
    expect(() => clearDraft("p1", broken)).not.toThrow();
  });

  it("describes its age in words", () => {
    const now = new Date().toISOString();
    expect(describeDraft({ data: {}, savedAt: now })).toMatch(/moment ago|draft from/);
    const old = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
    expect(describeDraft({ data: {}, savedAt: old })).toContain("hours ago");
  });
});
