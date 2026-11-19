import { Badge, StatusDot } from "../../components/status";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { useVizzyHost } from "./use-vizzy-host";

/**
 * Vizzy page: a thin shell strip plus the hosted Rea/Vizzy editor.
 *
 * The editor itself is a `WebContentsView` owned by the main process and
 * positioned over the rectangle below. It is not an iframe and not React; the
 * strip is the only Camxora UI on the page.
 */
export function VizzyPage() {
  const { state, busy, closed, containerRef, save, open, reload, closeEditor, openEditor } =
    useVizzyHost();

  const attached = state.attached && !closed;
  const saveLabel = state.dirty ? "Unsaved changes" : "Saved";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface-1 px-4">
        <Icon name="fa-film" size={14} className="text-text-muted" />
        <span className="text-meta text-text-muted">Vizzy</span>
        <span className="h-4 w-px bg-border" />

        <span className="max-w-[320px] truncate text-body font-medium text-text-primary">
          {state.projectName || "Untitled project"}
        </span>
        <StatusDot tone={state.dirty ? "warning" : "success"} label={attached ? saveLabel : "Not running"} />
        <span className="text-meta text-text-muted">{state.nodeCount} items</span>
        {state.fftTier !== "unknown" ? (
          <Badge tone="neutral">fft: {state.fftTier}</Badge>
        ) : null}
        {state.crossOriginIsolated ? <Badge tone="neutral">isolated</Badge> : null}

        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="primary"
            onClick={() => void save()}
            loading={busy === "save"}
            disabled={!attached}
          >
            Save
          </Button>
          <Button variant="secondary" onClick={() => void open()} loading={busy === "open"} disabled={!attached}>
            Open
          </Button>
          <Button variant="ghost" onClick={closeEditor} disabled={!attached}>
            Close
          </Button>
        </div>
      </div>

      {state.error ? (
        <div className="flex shrink-0 items-center gap-3 border-b border-danger/30 bg-danger-soft px-4 py-2 text-body-sm text-text-primary">
          <Icon name="fa-triangle-exclamation" size={14} className="text-danger" />
          <span className="min-w-0 flex-1 truncate">{state.error}</span>
          <Button variant="secondary" onClick={() => void reload()}>
            Reload editor
          </Button>
        </div>
      ) : null}

      <div className="relative min-h-0 flex-1">
        {closed ? (
          <div className="flex h-full items-center justify-center p-8">
            <div className="max-w-md text-center">
              <Icon name="fa-film" size={20} className="mx-auto text-text-muted" />
              <h2 className="mt-3 text-title font-semibold text-text-primary">Editor closed</h2>
              <p className="mt-1 text-body text-text-secondary">
                The Vizzy editor is stopped. Reopen it to continue working on this project.
              </p>
              <Button variant="primary" className="mt-4" onClick={openEditor}>
                Open editor
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* The native view is positioned over this rectangle. The text is the
                honest loading state behind it, visible only while it boots. */}
            <div
              ref={containerRef}
              className="absolute inset-0 flex items-center justify-center bg-bg"
              data-testid="vizzy-view-slot"
            >
              <div className="flex items-center gap-2 text-body-sm text-text-muted">
                <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                Starting the Vizzy editor
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
