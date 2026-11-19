import { useEffect, useMemo, useState } from "react";
import { Icon } from "../../components/icon";
import { classNames } from "../../lib/format";
import { bytesToDataUrl } from "./image-model";

export interface PreviewState {
  status: "empty" | "loading" | "ready" | "error";
  dataUrl: string | null;
  detail: string | null;
}

const EMPTY: PreviewState = { status: "empty", dataUrl: null, detail: null };

async function readFirst(candidates: string[]): Promise<PreviewState> {
  let lastError = "The output file is missing.";
  for (const candidate of candidates) {
    const result = await window.camxora.files.readImage(candidate);
    if (result.ok) {
      return {
        status: "ready",
        dataUrl: bytesToDataUrl(result.data.bytes, result.data.mime),
        detail: null,
      };
    }
    lastError = result.error.message || lastError;
  }
  return { status: "error", dataUrl: null, detail: lastError };
}

/** Loads the BG/TH output for the selected row off the UI thread. */
export function useImagePreview(candidates: string[], signature: string): PreviewState {
  const [state, setState] = useState<PreviewState>(EMPTY);
  const key = candidates.join("\u0000");
  const list = useMemo(() => (key ? key.split("\u0000") : []), [key]);

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
}: {
  title: string;
  subtitle: string;
  state: PreviewState;
  hasSelection: boolean;
  testId: string;
}) {
  return (
    <section className="card overflow-hidden" data-testid={testId} aria-label={title}>
      <header className="flex items-baseline justify-between gap-2 border-b border-border px-3 py-2">
        <h2 className="text-meta font-medium text-text-primary">{title}</h2>
        <span className="text-caption text-text-muted">{subtitle}</span>
      </header>
      <div className="relative flex h-[236px] items-center justify-center bg-surface-2">
        {state.status === "ready" && state.dataUrl ? (
          <img
            src={state.dataUrl}
            alt={`${title} output`}
            className="h-full w-full object-contain"
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
