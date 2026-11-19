import { useCallback, useEffect, useState } from "react";
import { Badge, StatusDot } from "../../components/status";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { VizzyExportMenu } from "./vizzy-export-menu";
import { VizzyExportStatus } from "./vizzy-export-status";
import { VizzyRendersPanel } from "./vizzy-renders-panel";
import { useVizzyExport } from "./use-vizzy-export";
import { useVizzyHost } from "./use-vizzy-host";
import { useVizzyRenders } from "./use-vizzy-renders";

type Panel = "export" | "renders" | null;

/**
 * Vizzy page: a thin shell strip plus the hosted Rea/Vizzy editor.
 *
 * The editor itself is a `WebContentsView` owned by the main process and
 * positioned over the rectangle below. It is not an iframe and not React; the
 * strip is the only Camxora UI on the page.
 *
 * Export and Renders open in a rail beside the editor, not on top of it: a
 * native child view always paints over DOM, so a floating popover would be
 * hidden. The rail shrinks the editor column and the host re-places the view.
 */
export function VizzyPage() {
  const { state, busy, closed, containerRef, save, open, reload, closeEditor, openEditor } =
    useVizzyHost();
  const exporter = useVizzyExport();
  const [panel, setPanel] = useState<Panel>(null);
  const renders = useVizzyRenders(panel === "renders");
  const {
    refresh: refreshRenders,
    reveal: revealRender,
    play: playRender,
    remove: removeRender,
  } = renders;

  const attached = state.attached && !closed;
  const saveLabel = state.dirty ? "Unsaved changes" : "Saved";

  // A finished export is a new file in `renders/`; refresh an open list.
  useEffect(() => {
    if (exporter.result && panel === "renders") void refreshRenders();
  }, [exporter.result, panel, refreshRenders]);

  const reveal = useCallback(
    (name: string) => {
      void revealRender(name);
    },
    [revealRender],
  );

  const togglePanel = (next: Panel): void => {
    setPanel((current) => (current === next ? null : next));
  };

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
        {state.projectWidth > 0 && state.projectHeight > 0 ? (
          <span className="text-meta text-text-muted">
            {state.projectWidth}×{state.projectHeight}
          </span>
        ) : null}
        {state.fftTier !== "unknown" ? (
          <Badge tone="neutral">fft: {state.fftTier}</Badge>
        ) : null}
        {state.crossOriginIsolated ? <Badge tone="neutral">isolated</Badge> : null}

        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => togglePanel("export")}
            disabled={!attached || exporter.running}
            loading={exporter.running}
            aria-expanded={panel === "export"}
            data-testid="vizzy-export-open"
          >
            <Icon name="fa-clapperboard" size={12} />
            Export
          </Button>
          <Button
            variant="ghost"
            onClick={() => togglePanel("renders")}
            aria-expanded={panel === "renders"}
            data-testid="vizzy-renders-open"
          >
            <Icon name="fa-photo-film" size={12} />
            Renders
          </Button>
          <span className="h-4 w-px bg-border" />
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

      <VizzyExportStatus
        running={exporter.running}
        progress={exporter.progress}
        result={exporter.result}
        error={exporter.error}
        onCancel={exporter.cancel}
        onDismiss={exporter.dismiss}
        onReveal={reveal}
        onOpenRenders={() => setPanel("renders")}
      />

      {state.error ? (
        <div className="flex shrink-0 items-center gap-3 border-b border-danger/30 bg-danger-soft px-4 py-2 text-body-sm text-text-primary">
          <Icon name="fa-triangle-exclamation" size={14} className="text-danger" />
          <span className="min-w-0 flex-1 truncate">{state.error}</span>
          <Button variant="secondary" onClick={() => void reload()}>
            Reload editor
          </Button>
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1">
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

        {panel ? (
          <aside className="flex w-[336px] shrink-0 flex-col gap-2 border-l border-border bg-bg p-3">
            {panel === "export" ? (
              <VizzyExportMenu
                open
                onClose={() => setPanel(null)}
                project={{
                  width: state.projectWidth,
                  height: state.projectHeight,
                  fps: state.projectFps,
                  duration: state.projectDuration,
                }}
                running={exporter.running}
                progress={exporter.progress}
                result={exporter.result}
                error={exporter.error}
                onStart={(settings) => void exporter.start(settings)}
                onCancel={exporter.cancel}
                onReveal={reveal}
                onOpenRenders={() => setPanel("renders")}
              />
            ) : (
              <VizzyRendersPanel
                items={renders.items}
                loading={renders.loading}
                error={renders.error}
                onClose={() => setPanel(null)}
                onRefresh={() => void refreshRenders()}
                onPlay={playRender}
                onReveal={(name) => void revealRender(name)}
                onDelete={removeRender}
              />
            )}
          </aside>
        ) : null}
      </div>
    </div>
  );
}
