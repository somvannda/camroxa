import { useCallback, useEffect, useRef, useState } from "react";
import type {
  VizzyExportOutcome,
  VizzyExportProgress,
  VizzyExportResult,
  VizzyExportSettingsInput,
  VizzyRenderTemplateRequest,
} from "../../../electron/shared/types";

export interface VizzyRunOutcome {
  status: "done" | "cancelled" | "failed";
  result: VizzyExportResult | null;
  message: string | null;
}

export interface VizzyExportHandle {
  /** Live progress for the current job, or the settled state of the last one. */
  progress: VizzyExportProgress | null;
  running: boolean;
  result: VizzyExportResult | null;
  /** Terminal failure or cancellation message; cleared by the next export. */
  error: string | null;
  start: (settings: VizzyExportSettingsInput) => Promise<VizzyRunOutcome>;
  /** Render one saved video template with a real run track. */
  startTemplate: (request: VizzyRenderTemplateRequest) => Promise<VizzyRunOutcome>;
  cancel: () => void;
  dismiss: () => void;
}

/**
 * Native export for the hosted editor, used by both the Export rail and the
 * Templates rail.
 *
 * The invoke resolves when the job settles (done/cancelled/failed); progress
 * arrives as a `vizzy:export:progress` event while it runs. Only one job can be
 * in flight, which the main process enforces too.
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

  const run = useCallback(
    async (invoke: () => Promise<{ ok: true; data: VizzyExportOutcome } | { ok: false; error: { message: string } }>): Promise<VizzyRunOutcome> => {
      if (runningRef.current) {
        return { status: "failed", result: null, message: "Another render is already running." };
      }
      runningRef.current = true;
      setRunning(true);
      setResult(null);
      setError(null);
      setProgress(null);
      try {
        const response = await invoke();
        if (!response.ok) {
          setError(response.error.message);
          setProgress(null);
          return { status: "failed", result: null, message: response.error.message };
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
          return { status: "done", result: outcome.result, message: null };
        }
        if (outcome.status === "cancelled") {
          const message = "Render cancelled. No file was written.";
          setError(message);
          setProgress(null);
          return { status: "cancelled", result: null, message };
        }
        setError(outcome.message);
        setProgress(null);
        return { status: "failed", result: null, message: outcome.message };
      } catch (cause) {
        const message = cause instanceof Error ? cause.message : "The render could not start.";
        setError(message);
        setProgress(null);
        return { status: "failed", result: null, message };
      } finally {
        runningRef.current = false;
        setRunning(false);
      }
    },
    [],
  );

  const start = useCallback(
    (settings: VizzyExportSettingsInput) => run(() => window.camxora.vizzy.export(settings)),
    [run],
  );

  const startTemplate = useCallback(
    (request: VizzyRenderTemplateRequest) =>
      run(() => window.camxora.vizzy.renderTemplate(request)),
    [run],
  );

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

  return { progress, running, result, error, start, startTemplate, cancel, dismiss };
}
