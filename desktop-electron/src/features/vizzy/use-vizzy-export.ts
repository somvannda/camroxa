import { useCallback, useEffect, useRef, useState } from "react";
import type {
  VizzyExportProgress,
  VizzyExportResult,
  VizzyExportSettingsInput,
} from "../../../electron/shared/types";

export interface VizzyExportHandle {
  /** Live progress for the current job, or the settled state of the last one. */
  progress: VizzyExportProgress | null;
  running: boolean;
  result: VizzyExportResult | null;
  /** Terminal failure or cancellation message; cleared by the next export. */
  error: string | null;
  start: (settings: VizzyExportSettingsInput) => Promise<void>;
  cancel: () => void;
  dismiss: () => void;
}

/**
 * Native export for the hosted editor.
 *
 * The invoke resolves when the job settles (done/cancelled/failed); progress
 * arrives as a `vizzy:export:progress` event while it runs. Only one export can
 * be in flight, which the main process enforces too.
 */
export function useVizzyExport(): VizzyExportHandle {
  const [progress, setProgress] = useState<VizzyExportProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<VizzyExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const runningRef = useRef(false);

  useEffect(() => {
    const subscribe = window.camxora?.vizzy?.onExportProgress;
    if (!subscribe) return;
    return subscribe((next) => {
      if (!runningRef.current) return;
      setProgress(next);
    });
  }, []);

  const start = useCallback(async (settings: VizzyExportSettingsInput) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    setResult(null);
    setError(null);
    setProgress(null);
    try {
      const response = await window.camxora.vizzy.export(settings);
      if (!response.ok) {
        setError(response.error.message);
        setProgress(null);
        return;
      }
      const outcome = response.data;
      if (outcome.status === "done") {
        setResult(outcome.result);
        setProgress({
          jobId: outcome.result.jobId,
          done: outcome.result.frames,
          total: outcome.result.frames,
          percent: 100,
          stage: "done",
        });
      } else if (outcome.status === "cancelled") {
        setError("Export cancelled. No file was written.");
        setProgress(null);
      } else {
        setError(outcome.message);
        setProgress(null);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The export could not start.");
      setProgress(null);
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  }, []);

  const cancel = useCallback(() => {
    if (!runningRef.current) return;
    const jobId = progress?.jobId;
    if (!jobId) return;
    setProgress((current) => (current ? { ...current, stage: "cancelling" } : current));
    void window.camxora.vizzy.cancelExport(jobId);
  }, [progress]);

  const dismiss = useCallback(() => {
    if (runningRef.current) return;
    setResult(null);
    setError(null);
    setProgress(null);
  }, []);

  return { progress, running, result, error, start, cancel, dismiss };
}
