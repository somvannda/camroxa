/**
 * Pure model behind the "Save as video template" dialog.
 *
 * The dialog only renders what this module returns: the binding option lists
 * (owner: the host snapshot), the pre-filled selection, the current field
 * errors and the kind/aspect check. Kept free of React and Electron so the
 * validation is unit-testable.
 */
import {
  bindingsFromSelection,
  emptySelection,
  firstBindingError,
  inferKind,
  kindAspectError,
  validateBindingSelection,
  type BindingErrors,
  type BindingOptions,
  type BindingSelection,
  type PipelineKind,
  type PipelineBindingsDraft,
} from "../../../electron/shared/pipeline";
import type { VizzyTemplateDraftInfo } from "../../../electron/shared/types";

export type { BindingOptions, BindingSelection, PipelineKind };
export { emptySelection, inferKind };

export interface TemplateDraftState {
  name: string;
  kind: PipelineKind;
  selection: BindingSelection;
}

export interface TemplateDraftErrors {
  /** A kind/aspect mismatch, shown above the form. */
  kind: string | null;
  /** One error per binding field, cleared as soon as the field changes. */
  fields: BindingErrors;
  /** First error in display order, for the guard and the summary. */
  summary: string | null;
}

/** Seed the dialog from `vizzy:template-options`. */
export function draftFromInfo(info: VizzyTemplateDraftInfo): TemplateDraftState {
  return {
    name: info.name,
    kind: info.kind,
    selection: { ...info.detected },
  };
}

export function templateDraftErrors(
  info: Pick<VizzyTemplateDraftInfo, "width" | "height" | "options">,
  draft: TemplateDraftState,
  name: string,
): TemplateDraftErrors {
  const trimmed = name.trim();
  const fields = validateBindingSelection(info.options, draft.selection);
  const kind = kindAspectError(draft.kind, info.width, info.height);
  const nameError = !trimmed
    ? "Give the template a name."
    : trimmed.length > 200
      ? "The name is too long (200 characters maximum)."
      : null;
  const fieldError = firstBindingError(fields);
  return {
    kind,
    fields,
    summary: kind ?? nameError ?? fieldError,
  };
}

/** True when every option list is empty: the template has nothing to bind. */
export function hasBindableNodes(options: BindingOptions): boolean {
  return Object.values(options).some((list) => list.length > 0);
}

/** The label of the selected node, for the compact summary line. */
export function optionLabel(
  options: BindingOptions,
  field: keyof BindingOptions,
  nodeId: string,
): string | null {
  if (!nodeId) return null;
  return options[field].find((option) => option.nodeId === nodeId)?.label ?? null;
}

/** The exact payload the save IPC writes, used by the dialog and the tests. */
export function bindingsForSave(draft: TemplateDraftState): PipelineBindingsDraft {
  return bindingsFromSelection(draft.selection);
}
