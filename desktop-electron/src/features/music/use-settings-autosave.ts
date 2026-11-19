import { useEffect, useRef, useState } from "react";
import { apiRequest } from "../../lib/api";
import { musicSettingsPatch, musicSettingsSnapshot, type MusicSettings } from "./music-settings";
import type { SaveStatus } from "./music-types";

export const SETTINGS_DEBOUNCE_MS = 400;
export const SAVED_STATUS_MS = 1800;

/**
 * Debounced PATCH /settings for music defaults.
 *
 * `enabled` flips true only after the bootstrap settings have been applied, so
 * the first render never writes the API values straight back. The snapshot
 * guard makes a save a no-op when the payload did not change, which is what
 * prevents the classic save → apply → save loop.
 */
export function useMusicSettingsAutosave(settings: MusicSettings, enabled: boolean) {
  const persistedRef = useRef<string | null>(null);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const idleTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const snapshot = musicSettingsSnapshot(settings);
    if (persistedRef.current === null) {
      persistedRef.current = snapshot;
      return;
    }
    if (snapshot === persistedRef.current) return;

    setStatus("saving");
    const timer = window.setTimeout(async () => {
      try {
        await apiRequest({
          method: "PATCH",
          path: "/settings",
          body: musicSettingsPatch(settings),
        });
        persistedRef.current = snapshot;
        setStatus("saved");
        if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
        idleTimer.current = window.setTimeout(() => setStatus("idle"), SAVED_STATUS_MS);
      } catch {
        setStatus("error");
      }
    }, SETTINGS_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [enabled, settings]);

  useEffect(
    () => () => {
      if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
    },
    [],
  );

  return status;
}
