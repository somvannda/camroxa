/**
 * Pure pipeline-template model shared by the main process and the shell.
 *
 * The save dialog, the host and the pipeline all need the same answers to
 * "which nodes can hold which binding" and "is this selection valid". Keeping
 * that logic here means the dialog can validate without IPC round trips and the
 * host validates the exact request it is about to write.
 *
 * No Node imports: this module is bundled into the renderer too.
 */

export type PipelineKind = "long" | "reel";

/** Every binding a saved video template can declare. Audio is implicit. */
export type PipelineBindingField =
  | "background"
  | "logo"
  | "title"
  | "artist"
  | "album"
  | "palette";

export const PIPELINE_BINDING_FIELDS: readonly PipelineBindingField[] = [
  "background",
  "logo",
  "title",
  "artist",
  "album",
  "palette",
] as const;

export const PIPELINE_FIELD_LABELS: Record<PipelineBindingField, string> = {
  background: "Background",
  logo: "Logo",
  title: "Title",
  artist: "Artist",
  album: "Album",
  palette: "Palette",
};

/** One selectable node for a binding. */
export interface BindingOption {
  nodeId: string;
  label: string;
  /** Node kind plus a short hint, shown beside the label. */
  detail: string;
}

export type BindingOptions = Record<PipelineBindingField, BindingOption[]>;

/** What the dialog holds: one node id per binding, or "" for "none". */
export type BindingSelection = Record<PipelineBindingField, string>;

export type BindingErrors = Partial<Record<PipelineBindingField, string>>;

export function emptySelection(): BindingSelection {
  return {
    background: "",
    logo: "",
    title: "",
    artist: "",
    album: "",
    palette: "",
  };
}

/** Long when the project is at least as wide as it is tall; reel otherwise. */
export function inferKind(width: number, height: number): PipelineKind {
  return width >= height ? "long" : "reel";
}

/**
 * The aspect must agree with the chosen kind. Square projects satisfy both, so
 * they may be saved either way.
 */
export function kindAspectError(
  kind: PipelineKind,
  width: number,
  height: number,
): string | null {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return "The project has no valid output size.";
  }
  if (kind === "long" && height > width) {
    return `A ${width}×${height} project is portrait; save it as a reel.`;
  }
  if (kind === "reel" && width > height) {
    return `A ${width}×${height} project is landscape; save it as a long video.`;
  }
  return null;
}

/** Structural binding payload written to `pipeline.json`. */
export interface PipelineBindingsDraft {
  audio: { mode: "replace" };
  background?: { nodeId: string; fit: "cover" | "contain" | "stretch" };
  logo?: { nodeId: string; circleMask: boolean };
  title?: { nodeId: string; maxChars: number; overflow: "clip" | "shrink" | "wrap" };
  artist?: { nodeId: string; maxChars: number; overflow: "clip" | "shrink" | "wrap" };
  album?: { nodeId: string; maxChars: number; overflow: "clip" | "shrink" | "wrap" };
  palette?: { nodeIds: string[]; mode: "accent" };
}

/** Overlay of the detected bindings onto the option lists. */
export interface DetectedBindingsLike {
  background?: { nodeId?: string } | undefined;
  logo?: { nodeId?: string } | undefined;
  title?: { nodeId?: string } | undefined;
  artist?: { nodeId?: string } | undefined;
  album?: { nodeId?: string } | undefined;
  palette?: { nodeIds?: string[] } | undefined;
}

function optionExists(options: BindingOptions, field: PipelineBindingField, nodeId: string): boolean {
  return options[field].some((option) => option.nodeId === nodeId);
}

/**
 * Seed the dialog from detection, dropping any detected node that is not a
 * compatible option (an old template, or a detector that got more permissive).
 */
export function selectionFromDetected(
  detected: DetectedBindingsLike,
  options: BindingOptions,
): BindingSelection {
  const selection = emptySelection();
  for (const field of PIPELINE_BINDING_FIELDS) {
    if (field === "palette") {
      const first = detected.palette?.nodeIds?.[0];
      if (first && optionExists(options, field, first)) selection.palette = first;
      continue;
    }
    const nodeId = detected[field]?.nodeId;
    if (nodeId && optionExists(options, field, nodeId)) selection[field] = nodeId;
  }
  return selection;
}

/**
 * Field-level validation for the save dialog.
 *
 * - a node can hold only one binding;
 * - a chosen node must exist in that binding's compatible option list;
 * - audio is implicit (`{ mode: "replace" }`) and always valid.
 */
export function validateBindingSelection(
  options: BindingOptions,
  selection: BindingSelection,
): BindingErrors {
  const errors: BindingErrors = {};
  const used = new Map<string, PipelineBindingField>();
  for (const field of PIPELINE_BINDING_FIELDS) {
    const nodeId = selection[field]?.trim();
    if (!nodeId) continue;
    if (!optionExists(options, field, nodeId)) {
      errors[field] = `That node is not a compatible ${PIPELINE_FIELD_LABELS[field].toLowerCase()} for this project.`;
      continue;
    }
    const owner = used.get(nodeId);
    if (owner) {
      errors[field] = `This node is already bound to ${PIPELINE_FIELD_LABELS[owner]}.`;
      continue;
    }
    used.set(nodeId, field);
  }
  return errors;
}

/** Convert a validated selection into the `pipeline.json` binding payload. */
export function bindingsFromSelection(selection: BindingSelection): PipelineBindingsDraft {
  const bindings: PipelineBindingsDraft = { audio: { mode: "replace" } };
  if (selection.background) {
    bindings.background = { nodeId: selection.background, fit: "cover" };
  }
  if (selection.logo) {
    bindings.logo = { nodeId: selection.logo, circleMask: true };
  }
  if (selection.title) {
    bindings.title = { nodeId: selection.title, maxChars: 80, overflow: "shrink" };
  }
  if (selection.artist) {
    bindings.artist = { nodeId: selection.artist, maxChars: 60, overflow: "clip" };
  }
  if (selection.album) {
    bindings.album = { nodeId: selection.album, maxChars: 60, overflow: "clip" };
  }
  if (selection.palette) {
    bindings.palette = { nodeIds: [selection.palette], mode: "accent" };
  }
  return bindings;
}

export function firstBindingError(errors: BindingErrors): string | null {
  for (const field of PIPELINE_BINDING_FIELDS) {
    if (errors[field]) return errors[field] as string;
  }
  return null;
}
