import { useEffect, useMemo, useState } from "react";
import { Icon } from "../../components/icon";
import { Select } from "../../components/select";
import { classNames } from "../../lib/format";
import { bytesToDataUrl, type PreviewCandidate } from "./image-model";

export interface PreviewState {
  status: "empty" | "loading" | "ready" | "error";
  dataUrl: string | null;
  detail: string | null;
}

const EMPTY: PreviewState = { status: "empty", dataUrl: null, detail: null };

async function readFirst(candidates: PreviewCandidate[]): Promise<PreviewState> {
  let lastError = "The output file is missing.";
  for (const candidate of candidates) {
    const local = await window.camxora.files.readImage(candidate.path);
    if (local.ok) {
      return {
        status: "ready",
        dataUrl: bytesToDataUrl(local.data.bytes, local.data.mime),
        detail: null,
      };
    }
    lastError = local.error.message || lastError;
    // AI images live on the server/B2, not in the run folder until something
    // caches them. Fetch the durable copy and write it beside the run audio.
    const remote = await window.camxora.files.readImageJob({
      jobId: candidate.jobId,
      path: candidate.path,
    });
    if (remote.ok) {
      return {
        status: "ready",
        dataUrl: bytesToDataUrl(remote.data.bytes, remote.data.mime),
        detail: null,
      };
    }
    lastError = remote.error.message || lastError;
  }
  return { status: "error", dataUrl: null, detail: lastError };
}

/** Loads the BG/TH output for the selected row off the UI thread. */
export function useImagePreview(candidates: PreviewCandidate[], signature: string): PreviewState {
  const [state, setState] = useState<PreviewState>(EMPTY);
  const key = candidates.map((candidate) => `${candidate.jobId}:${candidate.path}`).join("\u0000");
  const list = useMemo(
    () =>
      key
        ? key.split("\u0000").map((entry) => {
            const at = entry.indexOf(":");
            return { jobId: entry.slice(0, at), path: entry.slice(at + 1) };
          })
        : [],
    [key],
  );

  useEffect(() => {
    let cancelled = false;
    if (list.length === 0) {
      setState(EMPTY);
      return () => {
        cancelled = true;
      };
    }
    setState({ status: "loading", dataUrl: null, detail: null });
    void readFirst(list)
      .then((next) => {
        if (!cancelled) setState(next);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            dataUrl: null,
            detail: error instanceof Error ? error.message : "Preview unavailable.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [signature, list]);

  return state;
}

export function ImagePreviewCard({
  title,
  subtitle,
  state,
  hasSelection,
  testId,
  sourceValue,
  sourceOptions,
  onSourceChange,
  onOpen,
  onReveal,
}: {
  title: string;
  subtitle: string;
  state: PreviewState;
  hasSelection: boolean;
  testId: string;
  sourceValue?: string;
  sourceOptions?: Array<{ value: string; label: string }>;
  onSourceChange?: (value: string) => void;
  onOpen?: () => void;
  onReveal?: () => void;
}) {
  return (
    <section className="card overflow-hidden" data-testid={testId} aria-label={title}>
      <header className="flex items-baseline justify-between gap-2 border-b border-border px-3 py-2">
        <h2 className="text-meta font-medium text-text-primary">{title}</h2>
        <div className="flex min-w-0 items-center gap-1">
          <span className="truncate text-caption text-text-muted" title={subtitle}>
            {subtitle}
          </span>
          {onReveal ? (
            <button
              type="button"
              className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-[5px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
              aria-label={`Open ${title} folder`}
              title="Open output folder"
              onClick={onReveal}
            >
              <Icon name="fa-folder-open" size={12} />
            </button>
          ) : null}
        </div>
      </header>
      {sourceOptions && onSourceChange ? (
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5">
          <label className="text-caption text-text-muted" htmlFor={`${testId}-source`}>
            Source
          </label>
          <Select
            id={`${testId}-source`}
            controlSize="sm"
            value={sourceValue}
            options={sourceOptions}
            onValueChange={onSourceChange}
            wrapperClassName="flex-1"
          />
        </div>
      ) : null}
      <div className="relative flex h-[236px] items-center justify-center bg-surface-2">
        {state.status === "ready" && state.dataUrl ? (
          <img
            src={state.dataUrl}
            alt={`${title} output`}
            title={onOpen ? "Double-click to open the full image" : undefined}
            onDoubleClick={onOpen}
            className={classNames(
              "h-full w-full object-contain",
              onOpen && "cursor-pointer",
            )}
          />
        ) : (
          <div
            className={classNames(
              "flex flex-col items-center gap-2 px-4 text-center",
              state.status === "error" ? "text-danger" : "text-text-muted",
            )}
          >
            <Icon name="fa-image" size={18} />
            <p className="text-caption">
              {state.status === "loading"
                ? "Loading preview…"
                : state.status === "error"
                  ? "Preview unavailable."
                  : hasSelection
                    ? "No output for the selected row yet."
                    : "Select a queue row to preview the background/thumbnail output."}
            </p>
            {state.status === "error" && state.detail ? (
              <p className="text-caption text-text-muted">{state.detail}</p>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
