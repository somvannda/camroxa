import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/button";
import { Dialog, DialogContent } from "../../components/dialog";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { Select } from "../../components/select";
import type { PipelineKind } from "../../../electron/shared/pipeline";
import type {
  VizzyExportSettingsInput,
  VizzyTemplateDraftInfo,
} from "../../../electron/shared/types";
import { ExportSettingsFields } from "./vizzy-export-fields";
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
   * The render profile for this project. Always resolved: the rail's last
   * selection, or the project output with build defaults when the rail was
   * never used. Never inherited from another template.
   */
  exportSettings: VizzyExportSettingsInput;
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
 * The dialog always shows the render profile that will be used. Capturing it in
 * `pipeline.json` is opt-in: off, each render derives the same profile from the
 * project, so a template never inherits the rail state of another project.
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
  const [tab, setTab] = useState<"template" | "export">("template");
  const [settings, setSettings] = useState<VizzyExportSettingsInput>(exportSettings);
  // Seed only when the live draft arrives: the shell re-renders while the modal
  // is open, and re-seeding would discard edits made on the Export settings tab.
  const seedRef = useRef(exportSettings);
  seedRef.current = exportSettings;

  useEffect(() => {
    if (!info) return;
    setName(info.name);
    setKind(info.kind);
    setTemplateId("");
    setTab("template");
    setSettings({ ...seedRef.current });
  }, [info]);

  const existing = info?.existing.find((template) => template.id === templateId) ?? null;
  const overwriteOptions = info?.existing.filter((template) => template.kind === info.kind) ?? [];
  const outputWidth = settings.width ?? info?.width ?? 0;
  const outputHeight = settings.height ?? info?.height ?? 0;
  const draft: TemplateDraftState | null = info
    ? {
        name,
        kind,
        selection: info.detected,
        includeExportSettings: true,
        exportSettings: settings,
        templateId: templateId || undefined,
      }
    : null;
  // Kind is checked against the output that will actually be rendered: these
  // settings are saved, so a portrait profile cannot be a "long" template.
  const errors = info && draft
    ? templateDraftErrors({ ...info, width: outputWidth, height: outputHeight }, draft, name)
    : null;
  const canSave = Boolean(info && draft && errors && !errors.summary && !saving && !loading);
  const outputLine = formatExportSettings(settings);
  const contents = info?.contents ?? null;
  // Always show the profile: with capture off these are the defaults each render
  // derives from the project, so the visible numbers stay truthful either way.

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

                <div
                  role="tablist"
                  aria-label="Save as template sections"
                  className="flex gap-1 rounded-control border border-border bg-surface-2 p-1"
                >
                  {(
                    [
                      ["template", "Template"],
                      ["export", "Export settings"],
                    ] as const
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      role="tab"
                      aria-selected={tab === value}
                      data-testid={`vizzy-template-tab-${value}`}
                      onClick={() => setTab(value)}
                      className={
                        tab === value
                          ? "flex-1 rounded-[6px] bg-surface-1 px-3 py-1.5 text-body-sm font-medium text-text-primary shadow-sm"
                          : "flex-1 rounded-[6px] px-3 py-1.5 text-body-sm text-text-secondary hover:text-text-primary"
                      }
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {tab === "template" ? (
                  <div
                    role="tabpanel"
                    className="space-y-2 rounded-control border border-border bg-surface-2 p-3"
                  >
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
                          hint={
                            contents.spectrumLayers > 0 ? `${contents.spectrumLayers} layers` : null
                          }
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
                ) : (
                  <div
                    role="tabpanel"
                    className="space-y-2 rounded-control border border-border bg-surface-2 p-3"
                    data-testid="vizzy-template-export"
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-body-sm font-medium text-text-primary">Render settings</p>
                      <span className="shrink-0 text-caption text-text-muted">
                        {formatExportSettings(settings)}
                      </span>
                    </div>
                    <ExportSettingsFields value={settings} onChange={setSettings} />
                    <p className="text-caption text-text-muted">
                      These values are saved in pipeline.json and every pipeline render uses them.
                    </p>
                    <p className="text-caption text-text-muted">
                      Start/end trims are ignored; every render follows the song.
                    </p>
                  </div>
                )}

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
