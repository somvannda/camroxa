import { useCallback, useEffect, useMemo, useState } from "react";
import { StatusDot } from "../../components/status";
import { Button } from "../../components/button";
import { Dialog, DialogContent } from "../../components/dialog";
import { Icon } from "../../components/icon";
import { toast } from "../../components/toast";
import type {
  VizzyExportSettingsInput,
  VizzyTemplateDraftInfo,
} from "../../../electron/shared/types";
import { defaultExportSettings } from "./export-settings";
import { VizzyExportMenu } from "./vizzy-export-menu";
import { VizzyExportStatus } from "./vizzy-export-status";
import { VizzyRendersPanel } from "./vizzy-renders-panel";
import { VizzyTemplateDialog } from "./vizzy-template-dialog";
import { VizzyTemplatesPanel } from "./vizzy-templates-panel";
import { useVizzyExport } from "./use-vizzy-export";
import { useVizzyHost } from "./use-vizzy-host";
import { useVizzyRenders } from "./use-vizzy-renders";
import { useVizzyTemplates } from "./use-vizzy-templates";
import type { TemplateDraftState } from "./vizzy-template-model";

type Panel = "export" | "renders" | "templates" | null;

/**
 * Vizzy page: a thin shell strip plus the hosted Rea/Vizzy editor.
 *
 * The editor itself is a `WebContentsView` owned by the main process and
 * positioned over the rectangle below. It is not an iframe and not React; the
 * strip is the only Camxora UI on the page.
 *
 * Export, Renders and Templates open in a rail beside the editor, not on top of
 * it: a native child view always paints over DOM, so a floating popover would be
 * hidden. The rail shrinks the editor column and the host re-places the view.
 * The only modal (Save as video template) hides the view while it is open.
 */
export function VizzyPage() {
  const { state, busy, closed, containerRef, save, open, newProject, reload, closeEditor, openEditor } =
    useVizzyHost();
  const exporter = useVizzyExport();
  const [panel, setPanel] = useState<Panel>(null);
  const renders = useVizzyRenders(panel === "renders");
  const templates = useVizzyTemplates(panel === "templates");
  const { refresh: refreshRenders, reveal: revealRender, play: playRender, remove: removeRender } =
    renders;
  const { refresh: refreshTemplates, preview: previewTemplateOpen, openLibrary } = templates;

  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [exportProject, setExportProject] = useState<{
    width: number;
    height: number;
    fps: number;
    duration: number;
  } | null>(null);
  const [exportSettings, setExportSettings] = useState<VizzyExportSettingsInput | null>(null);
  const [templateInfo, setTemplateInfo] = useState<VizzyTemplateDraftInfo | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateLoadError, setTemplateLoadError] = useState<string | null>(null);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateSaveError, setTemplateSaveError] = useState<string | null>(null);
  const [renderingTemplateId, setRenderingTemplateId] = useState<string | null>(null);
  const [templateRenderResult, setTemplateRenderResult] = useState<{
    templateId: string;
    name: string;
  } | null>(null);
  const [templateRenderError, setTemplateRenderError] = useState<string | null>(null);

  const attached = state.attached && !closed;
  const saveLabel = state.dirty ? "Unsaved changes" : "Saved";

  const exportProjectInfo = useMemo(
    () => ({
      width: exportProject?.width ?? state.projectWidth,
      height: exportProject?.height ?? state.projectHeight,
      fps: exportProject?.fps ?? state.projectFps,
      duration: exportProject?.duration ?? state.projectDuration,
    }),
    [
      exportProject?.width,
      exportProject?.height,
      exportProject?.fps,
      exportProject?.duration,
      state.projectWidth,
      state.projectHeight,
      state.projectFps,
      state.projectDuration,
    ],
  );
  const templateExportSettings = useMemo(
    () => exportSettings ?? defaultExportSettings(exportProjectInfo),
    [exportSettings, exportProjectInfo],
  );

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

  const openExportPanel = useCallback(async () => {
    if (panel === "export") {
      setPanel(null);
      return;
    }
    // Read the live composition: the project duration becomes the audio length
    // after the track is decoded, which can be much later than the shell state.
    try {
      const response = await window.camxora.vizzy.projectInfo();
      if (response.ok && response.data) {
        setExportProject({
          width: response.data.width,
          height: response.data.height,
          fps: response.data.fps,
          duration: response.data.duration,
        });
      }
    } catch {
      // Fall back to the last reported shell state.
    }
    setPanel("export");
  }, [panel]);

  const openNewProject = useCallback(() => {
    if (!attached || exporter.running) return;
    setNewProjectOpen(true);
    void window.camxora?.vizzy?.setVisible(false);
  }, [attached, exporter.running]);

  const closeNewProject = useCallback(() => {
    setNewProjectOpen(false);
    void window.camxora?.vizzy?.setVisible(true);
  }, []);

  const confirmNewProject = useCallback(async () => {
    await newProject();
    setNewProjectOpen(false);
    void window.camxora?.vizzy?.setVisible(true);
    toast("New project started.", "info");
  }, [newProject]);

  /* video templates -------------------------------------------------- */

  const openTemplateDialog = useCallback(async () => {
    if (!attached || exporter.running) return;
    setTemplateDialogOpen(true);
    setTemplateInfo(null);
    setTemplateLoadError(null);
    setTemplateSaveError(null);
    setTemplateLoading(true);
    // A WebContentsView paints above shell DOM; hide it while the modal is up.
    void window.camxora?.vizzy?.setVisible(false);
    try {
      const response = await window.camxora.vizzy.templateOptions();
      if (response.ok) {
        setTemplateInfo(response.data);
      } else {
        setTemplateLoadError(response.error.message);
      }
    } catch (cause) {
      setTemplateLoadError(
        cause instanceof Error ? cause.message : "Could not read the current preview.",
      );
    } finally {
      setTemplateLoading(false);
    }
  }, [attached, exporter.running]);

  const closeTemplateDialog = useCallback(() => {
    if (templateSaving) return;
    setTemplateDialogOpen(false);
    void window.camxora?.vizzy?.setVisible(true);
  }, [templateSaving]);

  const saveTemplate = useCallback(
    async (draft: TemplateDraftState) => {
      setTemplateSaving(true);
      setTemplateSaveError(null);
      try {
        const response = await window.camxora.vizzy.saveTemplate({
          name: draft.name.trim(),
          kind: draft.kind,
          exportSettings: templateExportSettings,
        });
        if (!response.ok) {
          setTemplateSaveError(response.error.message);
          return;
        }
        setTemplateDialogOpen(false);
        void window.camxora?.vizzy?.setVisible(true);
        toast(`Saved video template ${response.data.name}.`, "success");
        setPanel("templates");
        await refreshTemplates();
      } catch (cause) {
        setTemplateSaveError(
          cause instanceof Error ? cause.message : "The template could not be saved.",
        );
      } finally {
        setTemplateSaving(false);
      }
    },
    [refreshTemplates, templateExportSettings],
  );

  const previewTemplate = useCallback(
    async (id: string) => {
      const opened = await previewTemplateOpen(id);
      if (!opened) return;
      toast(`Opened ${opened.name} in the editor.`, "success");
      setPanel(null);
    },
    [previewTemplateOpen],
  );

  const openTemplateLibrary = useCallback(async () => {
    const opened = await openLibrary();
    if (opened) toast("Creations browser opened in the editor.", "info");
  }, [openLibrary]);

  const renderTemplate = useCallback(
    async (id: string) => {
      if (exporter.running) return;
      setTemplateRenderError(null);
      setTemplateRenderResult(null);
      const picked = await window.camxora.files.pick({
        kind: "file",
        title: "Choose the run audio",
        filters: [
          { name: "Audio", extensions: ["mp3", "wav", "m4a", "flac", "ogg"] },
          { name: "All files", extensions: ["*"] },
        ],
      });
      if (!picked.ok) {
        setTemplateRenderError(picked.error.message);
        return;
      }
      const audioPath = picked.data[0];
      if (!audioPath) return;
      setRenderingTemplateId(id);
      const outcome = await exporter.startTemplate({ templateId: id, audioPath });
      setRenderingTemplateId(null);
      if (outcome.status === "done" && outcome.result) {
        setTemplateRenderResult({ templateId: id, name: outcome.result.name });
        toast(`Rendered ${outcome.result.name}.`, "success");
        void refreshRenders();
      } else if (outcome.status === "failed") {
        setTemplateRenderError(outcome.message ?? "The render failed.");
      }
    },
    [exporter, refreshRenders],
  );

  const deleteTemplate = useCallback(
    async (id: string) => {
      const removed = await templates.remove(id);
      if (removed) {
        toast("Video template deleted.", "success");
        if (templateRenderResult?.templateId === id) setTemplateRenderResult(null);
      }
      return removed;
    },
    [templates, templateRenderResult],
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-surface-1 px-4">
        <Icon name="fa-film" size={14} className="shrink-0 text-text-muted" />
        <span className="shrink-0 text-meta text-text-muted">Vizzy</span>
        <span className="h-4 w-px shrink-0 bg-border" />

        <span className="min-w-0 max-w-[220px] truncate text-body font-medium text-text-primary">
          {state.projectName || "Untitled project"}
        </span>
        <span className="shrink-0">
          <StatusDot
            tone={!state.ready && attached ? "accent" : state.dirty ? "warning" : "success"}
            label={attached ? (state.ready ? saveLabel : "Starting…") : "Not running"}
          />
        </span>
        <span className="hidden shrink-0 whitespace-nowrap text-meta text-text-muted min-[1440px]:inline">
          {state.nodeCount} {state.nodeCount === 1 ? "item" : "items"}
        </span>
        {state.projectWidth > 0 && state.projectHeight > 0 ? (
          <span className="hidden shrink-0 whitespace-nowrap text-meta text-text-muted min-[1440px]:inline">
            {state.projectWidth}×{state.projectHeight}
          </span>
        ) : null}

        <div className="ml-auto flex shrink-0 items-center gap-1">
          <Button
            variant="secondary"
            className="h-7 w-7 shrink-0 px-0"
            onClick={openNewProject}
            disabled={!attached || exporter.running}
            loading={busy === "new"}
            aria-label="New project"
            title="Start a new project"
            data-testid="vizzy-new-project"
          >
            <Icon name="fa-plus" size={12} />
          </Button>
          <Button
            variant="secondary"
            className="h-7 w-7 shrink-0 px-0"
            onClick={() => void open()}
            loading={busy === "open"}
            disabled={!attached}
            aria-label="Open project"
            title="Open a project file"
          >
            <Icon name="fa-folder-open" size={12} />
          </Button>
          <Button
            variant="primary"
            className="h-7 shrink-0 px-3 text-caption"
            onClick={() => void save()}
            loading={busy === "save"}
            disabled={!attached}
            title="Save the project file (Ctrl+S)"
          >
            Save project
          </Button>

          <span className="mx-1 h-4 w-px shrink-0 bg-border" />

          <Button
            variant="secondary"
            className="h-7 shrink-0 px-2.5 text-caption"
            onClick={() => void openExportPanel()}
            disabled={!attached || exporter.running}
            loading={exporter.running}
            aria-expanded={panel === "export"}
            title="Render this project to an MP4"
            data-testid="vizzy-export-open"
          >
            <Icon name="fa-clapperboard" size={12} />
            Export
          </Button>
          <Button
            variant="secondary"
            className="h-7 shrink-0 whitespace-nowrap px-2.5 text-caption"
            onClick={() => void openTemplateDialog()}
            disabled={!attached || exporter.running}
            title="Save this composition as a reusable video template"
            data-testid="vizzy-template-open"
          >
            <Icon name="fa-floppy-disk" size={12} />
            Save as template
          </Button>

          <span className="mx-1 h-4 w-px shrink-0 bg-border" />

          <Button
            variant="ghost"
            className="h-7 shrink-0 px-2 text-caption"
            onClick={() => togglePanel("templates")}
            aria-expanded={panel === "templates"}
            aria-label="Templates"
            title="Saved video templates"
            data-testid="vizzy-templates-open"
          >
            <Icon name="fa-layer-group" size={12} />
            Templates
          </Button>
          <Button
            variant="ghost"
            className="h-7 shrink-0 px-2 text-caption"
            onClick={() => togglePanel("renders")}
            aria-expanded={panel === "renders"}
            aria-label="Renders"
            title="Exported video files"
            data-testid="vizzy-renders-open"
          >
            <Icon name="fa-photo-film" size={12} />
            Renders
          </Button>

          <span className="mx-1 h-4 w-px shrink-0 bg-border" />

          <Button
            variant="ghost"
            className="h-7 w-7 shrink-0 px-0"
            onClick={closeEditor}
            disabled={!attached}
            aria-label="Close editor"
            title="Close the editor"
          >
            <Icon name="fa-xmark" size={13} />
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
        <div className="relative min-h-0 flex-1 p-2">
          {closed ? (
            <div className="flex h-full items-center justify-center rounded-card border border-border bg-surface-1 p-8">
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
                className="absolute inset-2 flex items-center justify-center overflow-hidden rounded-card border border-border bg-bg"
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
          <aside className="flex w-[336px] shrink-0 flex-col gap-2 overflow-y-auto border-l border-border bg-bg p-3">
            {panel === "export" ? (
              <VizzyExportMenu
                open
                onClose={() => setPanel(null)}
                project={exportProjectInfo}
                savedSettings={templateExportSettings}
                onSettingsChange={setExportSettings}
                running={exporter.running}
                progress={exporter.progress}
                result={exporter.result}
                error={exporter.error}
                onStart={(settings) => void exporter.start(settings)}
                onCancel={exporter.cancel}
                onReveal={reveal}
                onOpenRenders={() => setPanel("renders")}
              />
            ) : panel === "templates" ? (
              <VizzyTemplatesPanel
                items={templates.items}
                loading={templates.loading}
                error={templates.error}
                running={exporter.running}
                progress={exporter.progress}
                renderingId={renderingTemplateId}
                renderResult={templateRenderResult}
                renderError={templateRenderError}
                onClose={() => setPanel(null)}
                onRefresh={() => void refreshTemplates()}
                onSaveCurrent={() => void openTemplateDialog()}
                onPreview={(id) => void previewTemplate(id)}
                onRender={(id) => void renderTemplate(id)}
                onDelete={deleteTemplate}
                onLibrary={() => void openTemplateLibrary()}
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

      <Dialog
        open={newProjectOpen}
        onOpenChange={(next) => {
          if (!next) closeNewProject();
        }}
      >
        {newProjectOpen ? (
          <DialogContent
            title="Start a new project?"
            description="The current composition will be discarded. Save it first if you want to keep it."
          >
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="secondary" onClick={closeNewProject} disabled={busy === "new"}>
                Cancel
              </Button>
              <Button
                variant="danger"
                loading={busy === "new"}
                onClick={() => void confirmNewProject()}
                data-testid="vizzy-new-project-confirm"
              >
                Start new project
              </Button>
            </div>
          </DialogContent>
        ) : null}
      </Dialog>

      <VizzyTemplateDialog
        open={templateDialogOpen}
        info={templateInfo}
        loading={templateLoading}
        loadError={templateLoadError}
        saving={templateSaving}
        error={templateSaveError}
        onClose={closeTemplateDialog}
        onSave={(draft) => void saveTemplate(draft)}
      />
    </div>
  );
}
