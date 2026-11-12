/**
 * Offline draft storage (roadmap W2.3).
 *
 * The reference has no offline state at all: a cold load shows the browser's own
 * error page (spec §96), and a live session silently keeps working from cache (§82).
 * We keep the user's last edit burst instead, and offer it back on reload.
 *
 * The module is deliberately storage-agnostic so it can be unit-tested with a fake
 * `Storage` once the harness lands (W5.1).
 */

export type StudioDraft = {
  data: unknown;
  savedAt: string;
};

const PREFIX = "studio:draft:";

export function draftKey(projectId: string): string {
  return `${PREFIX}${projectId}`;
}

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function defaultStore(): Store | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    // Storage can throw in private modes and sandboxed frames.
    return null;
  }
}

export function saveDraft(
  projectId: string,
  data: unknown,
  store: Store | null = defaultStore()
): void {
  if (!store) return;
  try {
    const payload: StudioDraft = { data, savedAt: new Date().toISOString() };
    store.setItem(draftKey(projectId), JSON.stringify(payload));
  } catch {
    // A full quota must never break the editor.
  }
}

export function loadDraft(
  projectId: string,
  store: Store | null = defaultStore()
): StudioDraft | null {
  if (!store) return null;
  try {
    const raw = store.getItem(draftKey(projectId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StudioDraft;
    if (!parsed || typeof parsed !== "object" || !("data" in parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearDraft(projectId: string, store: Store | null = defaultStore()): void {
  if (!store) return;
  try {
    store.removeItem(draftKey(projectId));
  } catch {
    /* ignore */
  }
}

/** Human wording for the restore banner. */
export function describeDraft(draft: StudioDraft): string {
  const saved = new Date(draft.savedAt);
  if (Number.isNaN(saved.getTime())) return "an unsaved draft";
  const minutes = Math.round((Date.now() - saved.getTime()) / 60000);
  if (minutes < 1) return "an unsaved draft from a moment ago";
  if (minutes < 60) return `an unsaved draft from ${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  return `an unsaved draft from ${hours} hour${hours === 1 ? "" : "s"} ago`;
}
