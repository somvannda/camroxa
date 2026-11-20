import { useEffect, useState } from "react";
import { Button } from "../../components/button";
import { Dialog, DialogContent } from "../../components/dialog";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { Select } from "../../components/select";
import {
  PIPELINE_BINDING_FIELDS,
  PIPELINE_FIELD_LABELS,
  type BindingSelection,
  type PipelineBindingField,
  type PipelineKind,
} from "../../../electron/shared/pipeline";
import type { VizzyTemplateDraftInfo } from "../../../electron/shared/types";
import {
  templateDraftErrors,
  type TemplateDraftState,
} from "./vizzy-template-model";

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
 * "Save as video template": capture the exact preview plus the bindings the
 * pipeline may rebind for each run.
 *
 * It is a modal dialog rather than a rail because it is a one-shot decision.
 * The page hides the native editor view while it is open (a `WebContentsView`
 * always paints above shell DOM) and restores it on close.
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
  const [selection, setSelection] = useState<BindingSelection>({
    background: "",
    logo: "",
    title: "",
    artist: "",
    album: "",
    palette: "",
  });

  useEffect(() => {
    if (!info) return;
    setName(info.name);
    setKind(info.kind);
    setSelection({ ...info.detected });
  }, [info]);

  const draft: TemplateDraftState = { name, kind, selection };
  const errors = info ? templateDraftErrors(info, draft, name) : null;
  const canSave = Boolean(info && errors && !errors.summary && !saving && !loading);

  const updateBinding = (field: PipelineBindingField, value: string): void => {
    setSelection((current) => ({ ...current, [field]: value }));
  };

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
          description="The pipeline renders this exact project with the run audio. Choose which nodes it may rebind."
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
            ) : info ? (
              <>
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
                      data-testid="vizzy-template-kind"
                    />
                  </label>
                </div>

                <p className="text-caption text-text-muted" data-testid="vizzy-template-output">
                  Output: {info.width} × {info.height} · {info.fps} fps · duration = audio
                </p>

                <div className="space-y-2 rounded-control border border-border bg-surface-2 p-3">
                  <div className="flex items-center gap-2">
                    <span className="w-24 shrink-0 text-body-sm text-text-secondary">Audio</span>
                    <span className="text-body-sm text-text-primary" data-testid="vizzy-template-audio">
                      Run track replaces project audio
                    </span>
                    <span className="ml-auto text-caption text-text-muted">required</span>
                  </div>

                  {PIPELINE_BINDING_FIELDS.map((field) => {
                    const options = info.options[field];
                    const message = errors?.fields[field];
                    return (
                      <div key={field}>
                        <div className="flex items-center gap-2">
                          <span className="w-24 shrink-0 text-body-sm text-text-secondary">
                            {PIPELINE_FIELD_LABELS[field]}
                          </span>
                          <Select
                            value={selection[field]}
                            invalid={Boolean(message)}
                            options={[
                              { value: "", label: "— none —" },
                              ...options.map((option) => ({
                                value: option.nodeId,
                                label: `${option.label} · ${option.detail}`,
                              })),
                            ]}
                            onValueChange={(value) => updateBinding(field, value)}
                            aria-label={PIPELINE_FIELD_LABELS[field]}
                            wrapperClassName="min-w-0 flex-1"
                            data-testid={`vizzy-template-binding-${field}`}
                          />
                        </div>
                        {message ? (
                          <p
                            className="pl-[104px] text-caption text-danger"
                            role="alert"
                            data-testid={`vizzy-template-error-${field}`}
                          >
                            {message}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
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
                    Save template
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
