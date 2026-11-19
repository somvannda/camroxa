import { useCallback, useEffect, useRef, useState } from "react";
import type { DownloadSnapshot, IpcResult } from "../../../electron/shared/types";
import { DOWNLOADS_POLL_MS } from "./progress-format";
import { PollController } from "./progress-poll";

/**
 * PG-41/PG-46/PG-47/PG-48: the renderer only *reads* the coordinator.
 *
 * Snapshots refresh every 5 s while the page is visible, stop when it is
 * hidden, and every read is single-flight. `downloads:changed` only asks for an
 * early refresh; it never carries a URL or any credential.
 */
export interface DownloadQueueHandle {
  snapshot: DownloadSnapshot | null;
  error: string | null;
  loading: boolean;
  busy: boolean;
  refresh: () => Promise<void>;
  retry: (key: string) => Promise<string | null>;
  cancel: (key: string) => Promise<string | null>;
  reveal: (key: string) => Promise<string | null>;
  setPaused: (paused: boolean) => Promise<string | null>;
}

export function useDownloadQueue(): DownloadQueueHandle {
  const [snapshot, setSnapshot] = useState<DownloadSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const mounted = useRef(true);
  const controller = useRef<PollController | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const bridge = window.camxora?.downloads;
    if (!bridge) {
      if (mounted.current) setLoading(false);
      return;
    }
    try {
      const response = await bridge.list();
      if (!mounted.current) return;
      if (response.ok) {
        setSnapshot(response.data);
        setError(null);
      } else {
        // Keep the last snapshot so a transient failure never blanks the card.
        setError(response.error.message);
      }
    } catch (cause) {
      if (!mounted.current) return;
      setError(cause instanceof Error ? cause.message : "Could not read the download queue.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const poller = new PollController({
      poll: load,
      intervalMs: () => DOWNLOADS_POLL_MS,
    });
    controller.current = poller;
    if (!document.hidden) poller.start();

    const unsubscribe = window.camxora?.downloads?.onChange?.(() => {
      void poller.trigger();
    });

    return () => {
      unsubscribe?.();
      poller.stop();
      if (controller.current === poller) controller.current = null;
    };
  }, [load]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.hidden) {
        controller.current?.stop();
        return;
      }
      controller.current?.start();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  const refresh = useCallback(async () => {
    await controller.current?.trigger();
  }, []);

  const act = useCallback(
    async (run: () => Promise<IpcResult<DownloadSnapshot>>): Promise<string | null> => {
      setBusy(true);
      try {
        const response = await run();
        if (!response.ok) return response.error.message;
        if (mounted.current) {
          setSnapshot(response.data);
          setError(null);
        }
        return null;
      } catch (cause) {
        return cause instanceof Error ? cause.message : "The download action failed.";
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [],
  );

  const retry = useCallback(
    (key: string) => {
      const bridge = window.camxora?.downloads;
      if (!bridge) return Promise.resolve("Downloads are only available in the desktop app.");
      return act(() => bridge.retry(key));
    },
    [act],
  );

  const cancel = useCallback(
    (key: string) => {
      const bridge = window.camxora?.downloads;
      if (!bridge) return Promise.resolve("Downloads are only available in the desktop app.");
      return act(() => bridge.cancel(key));
    },
    [act],
  );

  const setPaused = useCallback(
    (paused: boolean) => {
      const bridge = window.camxora?.downloads;
      if (!bridge) return Promise.resolve("Downloads are only available in the desktop app.");
      return act(() => (paused ? bridge.stop() : bridge.start()));
    },
    [act],
  );

  const reveal = useCallback(async (key: string): Promise<string | null> => {
    const bridge = window.camxora?.downloads;
    if (!bridge) return "Downloads are only available in the desktop app.";
    try {
      const response = await bridge.reveal(key);
      return response.ok ? null : response.error.message;
    } catch (cause) {
      return cause instanceof Error ? cause.message : "That file could not be revealed.";
    }
  }, []);

  return { snapshot, error, loading, busy, refresh, retry, cancel, reveal, setPaused };
}
