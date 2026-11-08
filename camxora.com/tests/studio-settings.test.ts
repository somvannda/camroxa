import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_STUDIO_SETTINGS,
  dragApplyPlan,
  parseStudioSettings,
  readStudioSettings,
  writeStudioSettings,
} from "@/lib/studio-settings";

/** In-memory Storage stand-in; the real thing is just a string map. */
function storage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    map,
  };
}

describe("parseStudioSettings", () => {
  it("defaults when nothing is stored", () => {
    expect(parseStudioSettings(null)).toEqual(DEFAULT_STUDIO_SETTINGS);
    expect(DEFAULT_STUDIO_SETTINGS.ghostDrag).toBe(true);
  });

  it("keeps a stored false", () => {
    expect(parseStudioSettings('{"ghostDrag":false}')).toEqual({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false });
  });

  it("keeps a stored microphone and rejects an empty one", () => {
    expect(parseStudioSettings('{"inputDeviceId":"mic-2"}').inputDeviceId).toBe("mic-2");
    expect(parseStudioSettings('{"inputDeviceId":""}').inputDeviceId).toBeNull();
    expect(parseStudioSettings('{"inputDeviceId":7}').inputDeviceId).toBeNull();
  });

  it("parses the count-in flag", () => {
    expect(parseStudioSettings('{"countIn":true}').countIn).toBe(true);
    expect(parseStudioSettings('{"countIn":"yes"}').countIn).toBe(false);
    expect(parseStudioSettings("{}").countIn).toBe(false);
  });

  it("falls back per field instead of dropping the whole blob", () => {
    expect(parseStudioSettings('{"ghostDrag":"nope"}')).toEqual(DEFAULT_STUDIO_SETTINGS);
    expect(parseStudioSettings("{}")).toEqual(DEFAULT_STUDIO_SETTINGS);
  });

  it("survives malformed JSON", () => {
    expect(parseStudioSettings("{not json")).toEqual(DEFAULT_STUDIO_SETTINGS);
    expect(parseStudioSettings("null")).toEqual(DEFAULT_STUDIO_SETTINGS);
  });
});

describe("readStudioSettings / writeStudioSettings", () => {
  it("round-trips through storage", () => {
    const store = storage();
    writeStudioSettings({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false }, store);
    expect(readStudioSettings(store)).toEqual({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false });
  });

  it("uses the studio key and a readable payload", () => {
    const store = storage();
    writeStudioSettings({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false }, store);
    expect(JSON.parse(store.map.get("studio:settings") ?? "{}")).toEqual({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false });
  });

  it("never throws without storage (SSR, private mode)", () => {
    expect(readStudioSettings(null)).toEqual(DEFAULT_STUDIO_SETTINGS);
    expect(() => writeStudioSettings({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false }, null)).not.toThrow();
    const failing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(readStudioSettings(failing)).toEqual(DEFAULT_STUDIO_SETTINGS);
    expect(() => writeStudioSettings({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false }, failing)).not.toThrow();
  });

  it("does not mutate the shared default object", () => {
    const store = storage();
    writeStudioSettings({ ghostDrag: false, whatsThis: true, inputDeviceId: null, countIn: false }, store);
    expect(DEFAULT_STUDIO_SETTINGS.ghostDrag).toBe(true);
  });
});

describe("dragApplyPlan", () => {
  it("applies once on drop when ghost drag is on", () => {
    expect(dragApplyPlan(true)).toEqual({ duringMove: false, onDrop: true });
  });

  it("streams every move and nothing extra on drop when ghost drag is off", () => {
    expect(dragApplyPlan(false)).toEqual({ duringMove: true, onDrop: false });
  });

  it("is read for a specific gesture, so mid-drag changes cannot alter it", () => {
    const started = dragApplyPlan(true);
    // A settings change during the gesture would produce this plan instead…
    const later = dragApplyPlan(false);
    expect(started).not.toEqual(later);
    // …but the caller keeps the plan captured at gesture start (spec §22).
    expect(started.onDrop).toBe(true);
  });
});

describe("write failures", () => {
  it("swallows a quota error", () => {
    const setItem = vi.fn(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => writeStudioSettings({ ghostDrag: true, whatsThis: true, inputDeviceId: null, countIn: false }, { setItem })).not.toThrow();
    expect(setItem).toHaveBeenCalledOnce();
  });
});


