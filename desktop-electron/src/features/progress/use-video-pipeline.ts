import { useCallback, useEffect, useRef, useState } from "react";
import type { PipelineSnapshot } from "../../../electron/shared/types";

export interface VideoPipelineHandle {
  snapshot: PipelineSnapshot | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  refresh: () => Promise<void>;
  cancel: () => Promise<boolean>;
  start: () => Promise<boolean>;
  retry: (batchId?: string) => Promise<boolean>;
  force: (request: {
    mode: "force" | "repair" | "single";
    batchId?: string;
    jobIds?: string[];
  }) => Promise<boolean>;
  deleteExternal: (externalBatchId: string) => Promise<boolean>;
  clear: () => Promise<boolean>;
  reveal: (filePath: string) => Promise<boolean>;
}

const RUNNING_POLL_MS = 1_500;
const IDLE_POLL_MS = 8_000;

/**
 * The durable pipeline queue, read through IPC.
 *
 * The queue lives in SQLite, so leaving `/progress` and coming back shows the
 * same rows. `pipeline:changed` wakes the view immediately; a slow poll keeps
 * the rows honest if an event is missed.
 */
export function useVideoPipeline(): VideoPipelineHandle {
  const [snapshot, setSnapshot] = useState<PipelineSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);
  const running = snapshot?.running === true;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    try {
      const response = await window.camxora.pipeline.list();
      if (!mounted.current) return;
      if (response.ok) {
        setSnapshot(response.data);
        setError(null);
      } else {
        setError(response.error.message);
      }
    } catch (cause) {
      if (!mounted.current) return;
      setError(cause instanceof Error ? cause.message : "Could not read the video queue.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const subscribe = window.camxora?.pipeline?.onChange;
    if (!subscribe) return;
    return subscribe(() => {
      void refresh();
    });
  }, [refresh]);

  useEffect(() => {
    const timer = window.setInterval(
      () => void refresh(),
      running ? RUNNING_POLL_MS : IDLE_POLL_MS,
    );
    return () => window.clearInterval(timer);
  }, [refresh, running]);

  const act = useCallback(
    async (run: () => Promise<boolean>) => {
      setBusy(true);
      try {
        return await run();
      } finally {
        if (mounted.current) setBusy(false);
        await refresh();
      }
    },
    [refresh],
  );

  const cancel = useCallback(
    () =>
      act(async () => {
        const response = await window.camxora.pipeline.cancel();
        if (!response.ok) {
          setError(response.error.message);
          return false;
        }
        return response.data.cancelled;
      }),
    [act],
  );

  const retry = useCallback(
    (batchId?: string) =>
      act(async () => {
        const response = await window.camxora.pipeline.retry(batchId);
        if (!response.ok) {
          setError(response.error.message);
          return false;
        }
        return response.data.enqueued > 0;
      }),
    [act],
  );

  const start = useCallback(
    () =>
      act(async () => {
        const response = await window.camxora.pipeline.start();
        if (!response.ok) {
          setError(response.error.message);
          return false;
        }
        return response.data.started;
      }),
    [act],
  );

  const force = useCallback(
    (request: { mode: "force" | "repair" | "single"; batchId?: string; jobIds?: string[] }) =>
      act(async () => {
        const response = await window.camxora.pipeline.force(request);
        if (!response.ok) {
          setError(response.error.message);
          return false;
        }
        return response.data.enqueued > 0;
      }),
    [act],
  );

  const deleteExternal = useCallback(
    (externalBatchId: string) =>
      act(async () => {
        const response = await window.camxora.pipeline.deleteExternal(externalBatchId);
        if (!response.ok) {
          setError(response.error.message);
          return false;
        }
        return response.data.removed >= 0;
      }),
    [act],
  );

  const clear = useCallback(
    () =>
      act(async () => {
        const response = await window.camxora.pipeline.clear();
        if (!response.ok) {
          setError(response.error.message);
          return false;
        }
        return response.data.removed > 0;
      }),
    [act],
  );

  const reveal = useCallback(async (filePath: string) => {
    const response = await window.camxora.pipeline.reveal(filePath);
    if (!response.ok) {
      setError(response.error.message);
      return false;
    }
    return true;
  }, []);

  return { snapshot, loading, error, busy, refresh, cancel, start, retry, force, deleteExternal, clear, reveal };
}
