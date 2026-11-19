import { useState } from "react";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import type {
  VideoTemplateInfo,
  VizzyExportProgress,
} from "../../../electron/shared/types";
import { formatRenderDate } from "./vizzy-format";

export interface VizzyTemplatesPanelProps {
  items: VideoTemplateInfo[];
  loading: boolean;
  error: string | null;
  running: boolean;
  progress: VizzyExportProgress | null;
  /** Set while a specific template row is being rendered. */
  renderingId: string | null;
  renderResult: { templateId: string; name: string } | null;
  renderError: string | null;
  onClose: () => void;
  onRefresh: () => void;
  onSaveCurrent: () => void;
  onPreview: (id: string) => void;
  onRender: (id: string) => void;
  onDelete: (id: string) => Promise<boolean>;
  onLibrary: () => void;
}

/**
 * Templates rail: the saved video templates the pipeline can render.
 *
 * Like the Renders rail it shrinks the editor column instead of floating over
 * the native editor view. Rendering reuses the Export job/progress strip.
 */
export function VizzyTemplatesPanel({
  items,
  loading,
  error,
  running,
  progress,
  renderingId,
  renderResult,
  renderError,
  onClose,
  onRefresh,
  onSaveCurrent,
  onPreview,
  onRender,
  onDelete,
  onLibrary,
}: VizzyTemplatesPanelProps) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const remove = async (id: string): Promise<void> => {
    setBusyId(id);
    try {
      const deleted = await onDelete(id);
      if (deleted) setConfirming(null);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div
      className="flex h-full min-h-0 flex-col rounded-card border border-border bg-surface-1 shadow-2xl"
      role="region"
      aria-label="Video templates"
      data-testid="vizzy-templates-panel"
    >
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-3">
        <Icon name="fa-layer-group" size={13} className="text-text-muted" />
        <span className="text-caption uppercase tracking-wide text-text-muted">Templates</span>
        <span className="text-meta text-text-muted">{items.length}</span>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            aria-label="Refresh templates"
            className="flex h-6 w-6 items-center justify-center rounded-[6px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
            onClick={onRefresh}
            disabled={loading}
          >
            <Icon name="fa-rotate" size={12} />
          </button>
          <button
            type="button"
            aria-label="Close templates"
            className="flex h-6 w-6 items-center justify-center rounded-[6px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
            onClick={onClose}
          >
            <Icon name="fa-xmark" size={13} />
          </button>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
        <Button
          variant="primary"
          className="h-8 flex-1 px-2"
          onClick={onSaveCurrent}
          data-testid="vizzy-template-save-current"
        >
          <Icon name="fa-floppy-disk" size={12} />
          Save preview
        </Button>
        <Button
          variant="secondary"
          className="h-8 px-2"
          onClick={onLibrary}
          data-testid="vizzy-library-open"
        >
          <Icon name="fa-images" size={12} />
          Library
        </Button>
      </div>

      {running ? (
        <div className="shrink-0 space-y-1.5 border-b border-border px-3 py-2" data-testid="vizzy-template-render-progress">
          <div className="flex items-center gap-2 text-body-sm text-text-primary">
            <Icon name="fa-film" size={12} className="text-accent" />
            Rendering template
            <span className="ml-auto font-mono text-meta text-text-muted">
              {progress ? `${progress.percent}%` : "…"}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-300"
              style={{ width: `${progress?.percent ?? 0}%` }}
            />
          </div>
          <p className="truncate text-caption text-text-muted">
            {progress ? `${progress.stage} · ${progress.done}/${progress.total}` : "Preparing"}
          </p>
        </div>
      ) : renderResult ? (
        <div
          className="shrink-0 border-b border-border bg-success-soft/40 px-3 py-2"
          data-testid="vizzy-template-render-result"
        >
          <p className="flex items-center gap-1.5 text-body-sm text-text-primary">
            <Icon name="fa-circle-check" size={12} className="text-success" />
            Render saved
          </p>
          <p className="truncate text-caption text-text-muted">{renderResult.name}</p>
        </div>
      ) : renderError ? (
        <p className="shrink-0 border-b border-border px-3 py-2 text-caption text-danger" role="alert" data-testid="vizzy-template-render-error">
          {renderError}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto p-2" data-testid="vizzy-templates-list">
        {error ? (
          <p className="px-1 pb-2 text-meta text-danger" role="alert">
            {error}
          </p>
        ) : null}

        {items.length === 0 && !loading ? (
          <div className="px-2 py-6 text-center" data-testid="vizzy-templates-empty">
            <p className="text-body-sm text-text-muted">
              No saved video templates yet. Save the current preview to create one.
            </p>
            <Button variant="secondary" className="mt-3 h-8" onClick={onSaveCurrent}>
              Save as video template
            </Button>
          </div>
        ) : null}

        {items.map((item) => {
          const isConfirming = confirming === item.id;
          const busy = busyId === item.id;
          const rendering = running && renderingId === item.id;
          return (
            <div
              key={item.id}
              className="mb-1 rounded-control border border-transparent px-2 py-2 hover:border-border hover:bg-surface-2"
              data-testid="vizzy-template-row"
              data-id={item.id}
            >
              <div className="flex items-start gap-2">
                <div className="h-10 w-[64px] shrink-0 overflow-hidden rounded-[4px] border border-border bg-black">
                  {item.thumbnailUrl ? (
                    <img
                      src={item.thumbnailUrl}
                      alt={`${item.name} thumbnail`}
                      className="h-full w-full object-cover"
                      data-testid="vizzy-template-thumb"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center">
                      <Icon name="fa-image" size={12} className="text-text-muted" />
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <button
                    type="button"
                    className="block w-full truncate text-left text-body-sm text-text-primary hover:text-accent"
                    title={item.name}
                    onClick={() => onPreview(item.id)}
                    data-testid="vizzy-template-preview"
                  >
                    {item.name}
                  </button>
                  <p className="truncate text-caption text-text-muted">
                    <span className="capitalize">{item.kind}</span> · {item.width}×{item.height} ·{" "}
                    {item.fps} fps
                  </p>
                  <p className="truncate text-caption text-text-muted">
                    {formatRenderDate(new Date(item.createdAt).getTime())}
                  </p>
                </div>
              </div>
              <div className="mt-1 flex items-center justify-end gap-1">
                <Button
                  variant="ghost"
                  className="h-7 px-2"
                  onClick={() => onPreview(item.id)}
                  disabled={busy || running}
                  data-testid="vizzy-template-preview-action"
                >
                  Preview
                </Button>
                <Button
                  variant="secondary"
                  className="h-7 px-2"
                  loading={rendering}
                  onClick={() => onRender(item.id)}
                  disabled={busy || running}
                  data-testid="vizzy-template-render"
                >
                  Render
                </Button>
                <Button
                  variant="ghost"
                  className="h-7 px-2 text-danger hover:bg-danger-soft"
                  onClick={() => setConfirming(isConfirming ? null : item.id)}
                  disabled={busy || running}
                  data-testid="vizzy-template-delete"
                >
                  Delete
                </Button>
              </div>
              {isConfirming ? (
                <div
                  className="mt-1.5 flex items-center gap-2 rounded-control bg-danger-soft px-2 py-1.5"
                  data-testid="vizzy-template-delete-confirm-row"
                >
                  <span className="text-caption text-text-primary">Delete this template?</span>
                  <div className="ml-auto flex items-center gap-1">
                    <Button
                      variant="danger"
                      className="h-7 px-2"
                      loading={busy}
                      onClick={() => void remove(item.id)}
                      data-testid="vizzy-template-delete-confirm"
                    >
                      Delete
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-7 px-2"
                      onClick={() => setConfirming(null)}
                      disabled={busy}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="shrink-0 border-t border-border px-3 py-2 text-caption text-text-muted">
        Render asks for an audio file and writes the MP4 to the renders folder.
      </div>
    </div>
  );
}
