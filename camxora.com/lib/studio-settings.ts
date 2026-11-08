/**
 * Studio settings (reference §22).
 *
 * Only one setting was captured with its behaviour — **Ghost drag for arrangement
 * moves** — so only that one exists here. The other two captured sections (Window
 * management, Content) were never expanded; they are shown in the panel as "not
 * captured yet" rather than invented.
 *
 * Scope is the browser profile, not the project: these are editor preferences, so they
 * live in localStorage and never enter the arrangement document (which would make them
 * undoable and sync them to collaborators).
 */

export type StudioSettings = {
  /**
   * On: a drag holds the pre-drag audio and one apply lands on drop.
   * Off: every move frame is applied to the engine live.
   * Read once at gesture start, per §22.
   */
  ghostDrag: boolean;
  /**
   * What's This? (spec §7): hovering a control explains it. Default on, matching the
   * captured Learn menu state.
   */
  whatsThis: boolean;
  /**
   * Microphone used by Record (D-020). `null` follows the system default. Stored in the
   * browser profile, never in the project.
   */
  inputDeviceId: string | null;
  /** One bar of clicks before a take starts (D-021). Off by default. */
  countIn: boolean;
};

export const DEFAULT_STUDIO_SETTINGS: StudioSettings = {
  ghostDrag: true,
  whatsThis: true,
  inputDeviceId: null,
  countIn: false,
};

const KEY = "studio:settings";

type ReadableStorage = Pick<Storage, "getItem">;
type WritableStorage = Pick<Storage, "setItem">;

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** Parse stored settings, falling back per-field so a partial blob is still usable. */
export function parseStudioSettings(raw: string | null): StudioSettings {
  if (!raw) return { ...DEFAULT_STUDIO_SETTINGS };
  try {
    const parsed = JSON.parse(raw) as Partial<Record<keyof StudioSettings, unknown>>;
    if (!parsed || typeof parsed !== "object") return { ...DEFAULT_STUDIO_SETTINGS };
    return {
      ghostDrag:
        typeof parsed.ghostDrag === "boolean"
          ? parsed.ghostDrag
          : DEFAULT_STUDIO_SETTINGS.ghostDrag,
      whatsThis:
        typeof parsed.whatsThis === "boolean"
          ? parsed.whatsThis
          : DEFAULT_STUDIO_SETTINGS.whatsThis,
      inputDeviceId:
        typeof parsed.inputDeviceId === "string" && parsed.inputDeviceId
          ? parsed.inputDeviceId
          : null,
      countIn:
        typeof parsed.countIn === "boolean" ? parsed.countIn : DEFAULT_STUDIO_SETTINGS.countIn,
    };
  } catch {
    return { ...DEFAULT_STUDIO_SETTINGS };
  }
}

export function readStudioSettings(storage: ReadableStorage | null = browserStorage()): StudioSettings {
  if (!storage) return { ...DEFAULT_STUDIO_SETTINGS };
  try {
    return parseStudioSettings(storage.getItem(KEY));
  } catch {
    return { ...DEFAULT_STUDIO_SETTINGS };
  }
}

export function writeStudioSettings(
  settings: StudioSettings,
  storage: WritableStorage | null = browserStorage()
): void {
  if (!storage) return;
  try {
    storage.setItem(KEY, JSON.stringify(settings));
  } catch {
    /* private mode / quota: the setting stays session-only */
  }
}

/**
 * When a drag should touch the audio engine (§22).
 *
 * Ghost on: nothing during the gesture, one apply on drop. Ghost off: every move frame,
 * nothing extra on drop.
 */
export function dragApplyPlan(ghostDrag: boolean): { duringMove: boolean; onDrop: boolean } {
  return ghostDrag ? { duringMove: false, onDrop: true } : { duringMove: true, onDrop: false };
}
