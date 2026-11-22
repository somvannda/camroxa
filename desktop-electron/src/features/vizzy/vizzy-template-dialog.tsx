import { useEffect, useState } from "react";
import { Button } from "../../components/button";
import { Dialog, DialogContent } from "../../components/dialog";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { Select } from "../../components/select";
import type { PipelineKind } from "../../../electron/shared/pipeline";
import type { VizzyTemplateDraftInfo } from "../../../electron/shared/types";
import { templateDraftErrors, type TemplateDraftState } from "./vizzy-template-model";

export interface VizzyTemplateDialogProps {
  open: boolean;
  info: VizzyTemplateDraftInfo | null;
  loading: boolean;
  loadError: string | null;
  saving: boolean;
  error: string | null;
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
 * The page hides the native editor view while the modal is open because a
 * `WebContentsView` always paints above shell DOM.
 */
export function VizzyTemplateDialog({
  open,
  info,
  loading,
  loadError,
  saving,
  error,
  onClose,
  onSave,
}: VizzyTemplateDialogProps) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<PipelineKind>("long");
  const [templateId, setTemplateId] = useState("");

  useEffect(() => {
    if (!info) return;
    setName(info.name);
    setKind(info.kind);
    setTemplateId("");
  }, [info]);

  const existing = info?.existing.find((template) => template.id === templateId) ?? null;
  const overwriteOptions = info?.existing.filter((template) => template.kind === info.kind) ?? [];
  const draft: TemplateDraftState | null = info
    ? {
        name,
        kind,
        selection: info.detected,
        templateId: templateId || undefined,
      }
    : null;
  const errors = info && draft ? templateDraftErrors(info, draft, name) : null;
  const canSave = Boolean(info && draft && errors && !errors.summary && !saving && !loading);

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
          className="max-w-lg"
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
                  Output: {info.width} × {info.height} · {info.fps} fps · duration = audio
                </p>

                <div className="space-y-2 rounded-control border border-border bg-surface-2 p-3">
                  <p className="text-body-sm text-text-primary" data-testid="vizzy-template-audio">
                    Everything is saved: layers, objects, effects, spectrum, particles, analyzers,
                    automations, media and assets.
                  </p>
                  <p className="text-caption text-text-muted">
                    Per song, the pipeline only replaces the run audio and fills the detected
                    background, title, artist, album and palette nodes. Nodes that are not detected
                    stay exactly as designed.
                  </p>
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
