import { useEffect, useState } from "react";
import { Button } from "../../components/button";
import { Checkbox } from "../../components/checkbox";
import { Dialog, DialogContent } from "../../components/dialog";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { Select } from "../../components/select";
import type { PipelineKind } from "../../../electron/shared/pipeline";
import type {
  VizzyExportSettingsInput,
  VizzyTemplateDraftInfo,
} from "../../../electron/shared/types";
import { exportSettingRows } from "./export-settings";
import { formatExportSettings } from "./vizzy-format";
import { templateDraftErrors, type TemplateDraftState } from "./vizzy-template-model";

export interface VizzyTemplateDialogProps {
  open: boolean;
  info: VizzyTemplateDraftInfo | null;
  loading: boolean;
  loadError: string | null;
  saving: boolean;
  error: string | null;
  /**
   * Export rail settings for this project, or null when the rail has not been
   * used. Never inherited from another template.
   */
  exportSettings: VizzyExportSettingsInput | null;
  onClose: () => void;
  onSave: (draft: TemplateDraftState) => void;
}

/**
 * "Save as video template": one click saves the exact preview.
 *
 * There is no per-node selection. The whole snapshot (layers, objects, effects,
 * analyzers, automations, media, assets) is written by the host; at render time
 * it only replaces the run audio and the nodes it can detect automatically
 * (background, title, artist, album, palette).
 *
 * Export settings are opt-in: by default the pipeline follows the project
 * output with the default encoder, so a template never inherits the rail state
 * of whichever project happened to be open before it. The dialog always shows
 * the exact counts it will store and the exact render profile it will capture.
 *
 * The page hides the native editor view while the modal is open because a
 * `WebContentsView` always paints above shell DOM.
 */
function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string | null;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-caption text-text-muted">{label}</dt>
      <dd className="mt-0.5 flex items-baseline gap-1 text-body font-medium text-text-primary">
        <span className="text-tabular">{value}</span>
        {hint ? <span className="truncate text-caption font-normal text-text-muted">{hint}</span> : null}
      </dd>
    </div>
  );
}

export function VizzyTemplateDialog({
  open,
  info,
  loading,
  loadError,
  saving,
  error,
  exportSettings,
  onClose,
  onSave,
}: VizzyTemplateDialogProps) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<PipelineKind>("long");
  const [templateId, setTemplateId] = useState("");
  const [includeExport, setIncludeExport] = useState(false);

  useEffect(() => {
    if (!info) return;
    setName(info.name);
    setKind(info.kind);
    setTemplateId("");
    setIncludeExport(false);
  }, [info]);

  const existing = info?.existing.find((template) => template.id === templateId) ?? null;
  const overwriteOptions = info?.existing.filter((template) => template.kind === info.kind) ?? [];
  const captureExport = includeExport && Boolean(exportSettings);
  const outputWidth = captureExport ? (exportSettings?.width ?? info?.width ?? 0) : (info?.width ?? 0);
  const outputHeight = captureExport ? (exportSettings?.height ?? info?.height ?? 0) : (info?.height ?? 0);
  const draft: TemplateDraftState | null = info
    ? {
        name,
        kind,
        selection: info.detected,
        includeExportSettings: captureExport,
        templateId: templateId || undefined,
      }
    : null;
  // Kind is checked against the output that will actually be rendered, so a
  // captured portrait export cannot be saved as a "long" template.
  const errors = info && draft
    ? templateDraftErrors({ ...info, width: outputWidth, height: outputHeight }, draft, name)
    : null;
  const canSave = Boolean(info && draft && errors && !errors.summary && !saving && !loading);
  const outputLine =
    captureExport && exportSettings
      ? formatExportSettings(exportSettings)
      : `${info?.width ?? 0} × ${info?.height ?? 0} · ${info?.fps ?? 0} fps · default encoder`;
  const contents = info?.contents ?? null;
  const exportRows = captureExport && exportSettings ? exportSettingRows(exportSettings) : [];

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !saving) onClose();
      }}
    >
      {open ? (
        <DialogContent
          title="Save as video template"
          description="Saves everything in this composition. No node selection is needed."
          className="max-w-xl"
        >
          <div className="space-y-3" data-testid="vizzy-template-dialog">
            {loading ? (
              <div className="flex items-center gap-2 py-6 text-body-sm text-text-muted">
                <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                Reading the current preview…
              </div>
            ) : loadError ? (
              <p className="text-body-sm text-danger" role="alert" data-testid="vizzy-template-load-error">
                {loadError}
              </p>
            ) : info && draft ? (
              <>
                <label className="block space-y-1">
                  <span className="text-caption text-text-muted">Save to</span>
                  <Select
                    value={templateId}
                    options={[
                      { value: "", label: "New template" },
                      ...overwriteOptions.map((template) => ({
                        value: template.id,
                        label: `${template.name} (${template.kind})`,
                      })),
                    ]}
                    onValueChange={(value) => {
                      setTemplateId(value);
                      const target = info.existing.find((template) => template.id === value);
                      if (target) {
                        setName(target.name);
                        setKind(target.kind);
                      } else {
                        setName(info.name);
                        setKind(info.kind);
                      }
                    }}
                    data-testid="vizzy-template-target"
                  />
                </label>

                <div className="grid grid-cols-[1fr_150px] gap-3">
                  <label className="block space-y-1">
                    <span className="text-caption text-text-muted">Name</span>
                    <Input
                      value={name}
                      maxLength={200}
                      autoFocus
                      onChange={(event) => setName(event.target.value)}
                      data-testid="vizzy-template-name"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-caption text-text-muted">Kind</span>
                    <Select
                      value={kind}
                      options={[
                        { value: "long", label: "Long" },
                        { value: "reel", label: "Reel" },
                      ]}
                      onValueChange={(value) => setKind(value === "reel" ? "reel" : "long")}
                      disabled={Boolean(existing)}
                      data-testid="vizzy-template-kind"
                    />
                  </label>
                </div>

                <p className="text-caption text-text-muted" data-testid="vizzy-template-output">
                  Render output: {outputLine} · duration = audio
                </p>

                <div className="space-y-2 rounded-control border border-border bg-surface-2 p-3">
                  <p className="text-body-sm text-text-primary" data-testid="vizzy-template-audio">
                    Everything is saved: layers, objects, effects, spectrum, particles, analyzers,
                    automations, media and assets.
                  </p>
                  {contents ? (
                    <dl
                      className="grid grid-cols-3 gap-x-4 gap-y-2"
                      data-testid="vizzy-template-contents"
                    >
                      <Stat label="Layers" value={contents.layers} />
                      <Stat label="Objects" value={contents.objects} />
                      <Stat label="Effects" value={contents.effects} />
                      <Stat
                        label="Spectrum"
                        value={contents.spectrum}
                        hint={contents.spectrumLayers > 0 ? `${contents.spectrumLayers} layers` : null}
                      />
                      <Stat label="Particles" value={contents.particles} />
                      <Stat label="Analyzers" value={contents.analyzers} />
                      <Stat
                        label="Automations"
                        value={contents.automations}
                        hint={
                          contents.automationGroups > 0
                            ? `${contents.automationGroups} groups`
                            : null
                        }
                      />
                      <Stat label="Media" value={contents.media} />
                      <Stat label="Assets" value={contents.assets} />
                    </dl>
                  ) : null}
                  <p className="text-caption text-text-muted">
                    Per song, the pipeline only replaces the run audio and fills the detected
                    background, title, artist, album and palette nodes. Nodes that are not detected
                    stay exactly as designed.
                  </p>
                </div>

                <div
                  className="space-y-2 rounded-control border border-border bg-surface-2 p-3"
                  data-testid="vizzy-template-export"
                >
                  {exportSettings ? (
                    <>
                      <Checkbox
                        checked={includeExport}
                        onCheckedChange={setIncludeExport}
                        label="Save the Export settings with this template"
                        hint={formatExportSettings(exportSettings)}
                        data-testid="vizzy-template-export-toggle"
                      />
                      {exportRows.length ? (
                        <dl
                          className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-border pt-2"
                          data-testid="vizzy-template-export-summary"
                        >
                          {exportRows.map((row) => (
                            <div key={row.label} className="min-w-0">
                              <dt className="text-caption text-text-muted">{row.label}</dt>
                              <dd className="truncate text-meta text-text-primary" title={row.value}>
                                {row.value}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      ) : (
                        <p className="text-caption text-text-muted">
                          {`Not saved: pipeline renders use the project output and the default H.264 MP4 encoder. Turn this on to store ${formatExportSettings(exportSettings)}.`}
                        </p>
                      )}
                      <p className="text-caption text-text-muted">
                        Start/end trims are never stored; every render follows the song.
                      </p>
                    </>
                  ) : (
                    <p className="text-caption text-text-muted" data-testid="vizzy-template-export-none">
                      No Export settings were chosen for this project. Pipeline renders use the
                      project output ({info?.width ?? 0}×{info?.height ?? 0} · {info?.fps ?? 0} fps)
                      and the default H.264 MP4 encoder. Open Export first to capture a different
                      resolution, frame rate or quality with this template.
                    </p>
                  )}
                </div>

                {errors?.summary ? (
                  <p className="text-body-sm text-danger" role="alert" data-testid="vizzy-template-error">
                    {errors.summary}
                  </p>
                ) : null}
                {error ? (
                  <p className="text-body-sm text-danger" role="alert" data-testid="vizzy-template-save-error">
                    {error}
                  </p>
                ) : null}

                <div className="flex items-center justify-end gap-2 pt-1">
                  <Button
                    variant="ghost"
                    onClick={onClose}
                    disabled={saving}
                    data-testid="vizzy-template-cancel"
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    loading={saving}
                    disabled={!canSave}
                    onClick={() => canSave && onSave(draft)}
                    data-testid="vizzy-template-save"
                  >
                    <Icon name="fa-floppy-disk" size={12} />
                    {existing ? "Update template" : "Save template"}
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-body-sm text-text-muted">
                Open the Vizzy editor to save the current preview.
              </p>
            )}
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
